"""
Service quản lý các hoạt động đặt lệnh giao dịch bất đồng bộ (async).
Cho phép đặt lệnh mua/bán đồng thời trên nhiều sàn.
"""
import asyncio
from typing import Any, Optional
from utils.logger import log_info, log_error, log_warning
from utils.exceptions import OrderError, OrderFillTimeoutError, FuturesError
from configs import FIRST_ORDERS_FILL_TIMEOUT
from utils.helpers import extract_base_asset


class AsyncOrderService:
    """
    Lớp dịch vụ quản lý lệnh giao dịch bất đồng bộ.
    Sử dụng ccxt.pro để đặt lệnh đồng thời trên nhiều sàn.
    """

    def __init__(self, exchange_service: Any) -> None:
        """
        Khởi tạo dịch vụ quản lý lệnh async.

        Args:
            exchange_service (ExchangeService): Dịch vụ sàn giao dịch
        """
        self.exchange_service = exchange_service

    async def place_initial_orders(self, exchanges: list[str], symbol: str, amount_per_exchange: float,
                                   price, notification_service=None):
        """
        Đặt lệnh mua ban đầu đồng thời trên tất cả các sàn.

        Args:
            exchanges (list): Danh sách tên sàn giao dịch
            symbol (str): Ký hiệu cặp giao dịch
            amount_per_exchange (float): Số lượng mỗi lệnh
            price (float): Giá mua
            notification_service: Dịch vụ thông báo

        Returns:
            bool: True nếu tất cả lệnh đã khớp
        """
        base_asset = extract_base_asset(symbol)

        # Đặt lệnh đồng thời trên tất cả sàn
        async def _place_one(exchange_id):
            try:
                order = await self.exchange_service.async_create_limit_buy_order(
                    exchange_id, symbol, amount_per_exchange, price
                )
                log_info(
                    f"Đặt lệnh giới hạn mua {round(amount_per_exchange, 3)} "
                    f"{base_asset} ở giá {price} gửi đến {exchange_id}."
                )
                if notification_service:
                    notification_service.send_message(
                        f"Đặt lệnh giới hạn mua {round(amount_per_exchange, 3)} "
                        f"{base_asset} ở giá {price} gửi đến {exchange_id}."
                    )
                return exchange_id, order, None
            except Exception as e:
                return exchange_id, None, e

        # Đặt tất cả lệnh đồng thời
        results = await asyncio.gather(*[_place_one(ex) for ex in exchanges])

        # Kiểm tra lỗi
        failed = [(ex, err) for ex, order, err in results if err]
        if failed:
            for ex, err in failed:
                log_error(f"Lỗi đặt lệnh ban đầu trên {ex}: {str(err)}")
            if len(failed) == len(exchanges):
                raise OrderError("all", "initial buy", "Tất cả lệnh đều thất bại")

        log_info("Tất cả lệnh đã được gửi đồng thời.")

        # Chờ lệnh khớp
        return await self._wait_for_initial_fills(
            exchanges, symbol, notification_service
        )

    async def _wait_for_initial_fills(self, exchanges: list[str], symbol: str,
                                      notification_service=None):
        """
        Chờ tất cả lệnh ban đầu khớp (async polling).

        Args:
            exchanges (list): Danh sách sàn
            symbol (str): Cặp giao dịch
            notification_service: Dịch vụ thông báo

        Returns:
            bool: True nếu tất cả lệnh đã khớp
        """
        timeout_seconds = FIRST_ORDERS_FILL_TIMEOUT
        filled = set()
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            # Kiểm tra đồng thời trên tất cả sàn chưa khớp
            pending = [ex for ex in exchanges if ex not in filled]
            if not pending:
                return True

            check_tasks = []
            for exchange_id in pending:
                check_tasks.append(self._check_fill(exchange_id, symbol))

            results = await asyncio.gather(*check_tasks, return_exceptions=True)

            for exchange_id, result in zip(pending, results):
                if isinstance(result, Exception):
                    log_error(f"Lỗi kiểm tra lệnh trên {exchange_id}: {str(result)}")
                    continue
                if result:  # is_filled
                    filled.add(exchange_id)
                    log_info(f"Lệnh trên {exchange_id} đã được điền.")
                    if notification_service:
                        notification_service.send_message(
                            f"Lệnh trên {exchange_id} đã được điền."
                        )

            if len(filled) == len(exchanges):
                return True

            await asyncio.sleep(1.8)

        # Hết thời gian - xử lý lệnh chưa khớp
        unfilled = [ex for ex in exchanges if ex not in filled]
        if unfilled:
            message = (
                f"Lệnh không được điền trong {FIRST_ORDERS_FILL_TIMEOUT // 60} phút "
                f"trên: {', '.join(unfilled)}. Hủy và bán."
            )
            log_warning(message)
            if notification_service:
                notification_service.send_message(message)

            # Bán khẩn cấp trên sàn đã khớp
            if filled:
                await self.async_emergency_sell(symbol, list(filled))

            # Hủy lệnh trên sàn chưa khớp
            await self._cancel_unfilled_orders(unfilled, symbol)
            return False

        return True

    async def _check_fill(self, exchange_id: str, symbol: str) -> bool:
        """Kiểm tra lệnh đã khớp chưa."""
        open_orders = await self.exchange_service.async_fetch_open_orders(
            exchange_id, symbol
        )
        return len(open_orders) == 0

    async def _cancel_unfilled_orders(self, exchanges: list[str], symbol: str) -> None:
        """Hủy lệnh chưa khớp trên các sàn."""
        for exchange_id in exchanges:
            try:
                open_orders = await self.exchange_service.async_fetch_open_orders(
                    exchange_id, symbol
                )
                for order in open_orders:
                    await self.exchange_service.async_cancel_order(
                        exchange_id, order['id'], symbol
                    )
                    log_info(f"Đã hủy lệnh {order['id']} trên {exchange_id}.")
            except Exception as e:
                log_error(f"Lỗi khi hủy lệnh trên {exchange_id}: {str(e)}")

    async def place_arbitrage_orders(self, min_ask_ex: str, max_bid_ex: str, symbol: str,
                                     amount, min_ask_price, max_bid_price,
                                     notification_service=None):
        """
        Đặt lệnh chênh lệch giá đồng thời: mua + bán cùng lúc.

        Args:
            min_ask_ex (str): Sàn mua (giá thấp nhất)
            max_bid_ex (str): Sàn bán (giá cao nhất)
            symbol (str): Cặp giao dịch
            amount (float): Số lượng
            min_ask_price (float): Giá mua
            max_bid_price (float): Giá bán
            notification_service: Dịch vụ thông báo

        Returns:
            dict: Kết quả giao dịch bao gồm thông tin slippage:
                - success (bool): True nếu ít nhất 1 lệnh thành công
                - buy_order (dict|None): Thông tin lệnh mua
                - sell_order (dict|None): Thông tin lệnh bán
                - expected_buy_price (float): Giá mua kỳ vọng
                - expected_sell_price (float): Giá bán kỳ vọng
                - actual_buy_price (float|None): Giá mua thực tế
                - actual_sell_price (float|None): Giá bán thực tế
                - buy_slippage_pct (float): Slippage mua (%)
                - sell_slippage_pct (float): Slippage bán (%)
                - total_slippage_usd (float): Tổng slippage (USD)
        """
        base_asset = extract_base_asset(symbol)

        fill_result = {
            'success': False,
            'buy_order': None,
            'sell_order': None,
            'expected_buy_price': min_ask_price,
            'expected_sell_price': max_bid_price,
            'actual_buy_price': None,
            'actual_sell_price': None,
            'buy_slippage_pct': 0.0,
            'sell_slippage_pct': 0.0,
            'total_slippage_usd': 0.0,
        }

        try:
            # Đặt lệnh mua + bán ĐỒNG THỜI
            buy_task = self.exchange_service.async_create_limit_buy_order(
                min_ask_ex, symbol, amount, min_ask_price
            )
            sell_task = self.exchange_service.async_create_limit_sell_order(
                max_bid_ex, symbol, amount, max_bid_price
            )

            results = await asyncio.gather(buy_task, sell_task, return_exceptions=True)
            buy_result, sell_result = results

            # Kiểm tra kết quả
            buy_success = not isinstance(buy_result, Exception)
            sell_success = not isinstance(sell_result, Exception)

            if buy_success:
                fill_result['buy_order'] = buy_result
                # Lấy giá thực tế từ order response (average/price)
                actual_buy = self._extract_fill_price(buy_result, min_ask_price)
                fill_result['actual_buy_price'] = actual_buy
                log_info(
                    f"Lệnh mua giới hạn đã gửi đến {min_ask_ex} "
                    f"cho {amount} {base_asset} ở giá {min_ask_price}"
                )
            else:
                log_error(f"Lỗi đặt lệnh mua trên {min_ask_ex}: {str(buy_result)}")

            if sell_success:
                fill_result['sell_order'] = sell_result
                actual_sell = self._extract_fill_price(sell_result, max_bid_price)
                fill_result['actual_sell_price'] = actual_sell
                log_info(
                    f"Lệnh bán giới hạn đã gửi đến {max_bid_ex} "
                    f"cho {amount} {base_asset} ở giá {max_bid_price}"
                )
            else:
                log_error(f"Lỗi đặt lệnh bán trên {max_bid_ex}: {str(sell_result)}")

            if notification_service:
                notification_service.send_message(
                    f"Đặt lệnh chênh lệch giá (async):\n"
                    f"- Mua: {min_ask_ex} {amount} {base_asset} @ {min_ask_price} "
                    f"{'✅' if buy_success else '❌'}\n"
                    f"- Bán: {max_bid_ex} {amount} {base_asset} @ {max_bid_price} "
                    f"{'✅' if sell_success else '❌'}"
                )

            if not buy_success and not sell_success:
                raise OrderError(f"{min_ask_ex}/{max_bid_ex}", "arbitrage",
                                 "Cả hai lệnh đều thất bại")

            # Xử lý lệch vị thế: một lệnh thành công, một lệnh thất bại
            if buy_success and not sell_success:
                log_warning(f"Sell thất bại trên {max_bid_ex}, đang đảo lệnh mua trên {min_ask_ex}...")
                await self._emergency_reverse_buy(min_ask_ex, symbol, amount, notification_service)
                fill_result['success'] = False
                return fill_result

            if sell_success and not buy_success:
                log_warning(f"Buy thất bại trên {min_ask_ex}, đang đảo lệnh bán trên {max_bid_ex}...")
                await self._emergency_reverse_sell(max_bid_ex, symbol, amount, notification_service)
                fill_result['success'] = False
                return fill_result

            fill_result['success'] = True

            # Chờ lệnh khớp (tối đa 3 phút) và cập nhật giá thực tế
            wait_result = await self._wait_for_arbitrage_fills(
                min_ask_ex, max_bid_ex, symbol, amount,
                buy_success, sell_success, notification_service
            )

            # Sau khi lệnh khớp, lấy giá fill thực tế từ closed orders
            if wait_result:
                await self._update_fill_prices(
                    fill_result, min_ask_ex, max_bid_ex, symbol, amount
                )

            # Tính slippage
            self._calculate_slippage(fill_result, amount)

            return fill_result

        except OrderError:
            raise
        except Exception as e:
            raise OrderError(f"{min_ask_ex}/{max_bid_ex}", "arbitrage", str(e))

    async def _wait_for_arbitrage_fills(self, min_ask_ex: str, max_bid_ex: str, symbol: str,
                                        amount, buy_placed, sell_placed,
                                        notification_service=None):
        """
        Chờ lệnh arbitrage khớp (async).

        Args:
            min_ask_ex (str): Sàn mua
            max_bid_ex (str): Sàn bán
            symbol (str): Cặp giao dịch
            amount (float): Số lượng
            buy_placed (bool): Lệnh mua đã đặt thành công
            sell_placed (bool): Lệnh bán đã đặt thành công
            notification_service: Dịch vụ thông báo

        Returns:
            bool: True nếu thành công
        """
        cancel_timeout = 180  # 3 phút
        start_time = asyncio.get_event_loop().time()
        buy_filled = not buy_placed  # Nếu không đặt được = coi như đã xử lý
        sell_filled = not sell_placed

        while (asyncio.get_event_loop().time() - start_time) < cancel_timeout:
            await asyncio.sleep(2)

            # Kiểm tra đồng thời 2 sàn
            tasks = []
            if buy_placed and not buy_filled:
                tasks.append(('buy', self._check_fill(min_ask_ex, symbol)))
            if sell_placed and not sell_filled:
                tasks.append(('sell', self._check_fill(max_bid_ex, symbol)))

            if not tasks:
                return True

            results = await asyncio.gather(
                *[t[1] for t in tasks], return_exceptions=True
            )

            for (side, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    continue
                if result:
                    if side == 'buy':
                        buy_filled = True
                        log_info(f"Lệnh mua trên {min_ask_ex} đã được điền!")
                        if notification_service:
                            notification_service.send_message(
                                f"Lệnh mua trên {min_ask_ex} đã được điền!"
                            )
                    elif side == 'sell':
                        sell_filled = True
                        log_info(f"Lệnh bán trên {max_bid_ex} đã được điền!")
                        if notification_service:
                            notification_service.send_message(
                                f"Lệnh bán trên {max_bid_ex} đã được điền!"
                            )

            if buy_filled and sell_filled:
                return True

        # Xử lý timeout
        await self._handle_arbitrage_timeout(
            min_ask_ex, max_bid_ex, symbol, buy_filled, sell_filled,
            notification_service
        )

        return buy_filled and sell_filled

    async def _handle_arbitrage_timeout(self, min_ask_ex: str, max_bid_ex: str, symbol: str,
                                        buy_filled, sell_filled,
                                        notification_service=None):
        """Xử lý khi lệnh arbitrage timeout."""
        buy_orders = await self.exchange_service.async_fetch_open_orders(
            min_ask_ex, symbol
        ) if not buy_filled else []
        sell_orders = await self.exchange_service.async_fetch_open_orders(
            max_bid_ex, symbol
        ) if not sell_filled else []

        if buy_orders and not sell_orders:
            # Lệnh mua chưa khớp, bán đã khớp => hủy mua + mua market bù
            log_warning(f"Lệnh mua trên {min_ask_ex} không khớp trong 3 phút.")
            await self.exchange_service.async_cancel_order(
                min_ask_ex, buy_orders[0]['id'], symbol
            )
            try:
                closed = await self.exchange_service.async_fetch_closed_orders(
                    max_bid_ex, symbol
                )
                if closed:
                    await self.exchange_service.async_create_market_buy_order(
                        max_bid_ex, symbol, closed[-1]['filled']
                    )
                    log_info(f"Đã tạo lệnh mua market bù trên {max_bid_ex}.")
            except Exception as e:
                log_error(f"Lỗi khi bù lệnh: {str(e)}")

        elif sell_orders and not buy_orders:
            # Lệnh bán chưa khớp, mua đã khớp => hủy bán + bán market bù
            log_warning(f"Lệnh bán trên {max_bid_ex} không khớp trong 3 phút.")
            await self.exchange_service.async_cancel_order(
                max_bid_ex, sell_orders[0]['id'], symbol
            )
            try:
                closed = await self.exchange_service.async_fetch_closed_orders(
                    min_ask_ex, symbol
                )
                if closed:
                    await self.exchange_service.async_create_market_sell_order(
                        min_ask_ex, symbol, closed[-1]['filled']
                    )
                    log_info(f"Đã tạo lệnh bán market bù trên {min_ask_ex}.")
            except Exception as e:
                log_error(f"Lỗi khi bù lệnh: {str(e)}")

        elif buy_orders and sell_orders:
            # Cả hai chưa khớp => hủy cả hai
            log_warning("2 lệnh không khớp trong 3 phút. Đang hủy...")
            await asyncio.gather(
                self.exchange_service.async_cancel_order(
                    min_ask_ex, buy_orders[0]['id'], symbol
                ),
                self.exchange_service.async_cancel_order(
                    max_bid_ex, sell_orders[0]['id'], symbol
                ),
                return_exceptions=True
            )
            log_info("Đã hủy cả hai lệnh.")

    async def async_emergency_sell(self, symbol: str, exchanges: list[str]) -> None:
        """
        Bán khẩn cấp tất cả trên nhiều sàn đồng thời.

        Args:
            symbol (str): Cặp giao dịch
            exchanges (list): Danh sách sàn

        Returns:
            bool: True nếu thành công
        """
        tasks = [
            self.exchange_service.async_emergency_convert(exchange_id, symbol)
            for exchange_id in exchanges
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for exchange_id, result in zip(exchanges, results):
            if isinstance(result, Exception):
                log_error(f"Lỗi bán khẩn cấp async trên {exchange_id}: {str(result)}")
            else:
                log_info(f"Đã bán khẩn cấp thành công trên {exchange_id}")

        return True

    async def place_futures_short_order(self, exchange_id: str, symbol: str, amount: float,
                                        leverage=1):
        """
        Đặt lệnh Short futures (async).

        Args:
            exchange_id (str): ID sàn giao dịch
            symbol (str): Ký hiệu cặp giao dịch
            amount (float): Số lượng
            leverage (int): Đòn bẩy

        Returns:
            dict: Thông tin lệnh
        """
        try:
            if not symbol.endswith(':USDT'):
                symbol = f"{extract_base_asset(symbol)}:USDT"
            params = {'leverage': leverage}
            order = await self.exchange_service.async_create_futures_order(
                exchange_id, symbol, 'market', 'sell', amount, params
            )
            log_info(
                f"Đã đặt lệnh short async trên {exchange_id} cho {amount} "
                f"{extract_base_asset(symbol)} với đòn bẩy {leverage}x"
            )
            return order
        except Exception as e:
            raise FuturesError(exchange_id, f"Async: Không thể đặt lệnh short: {str(e)}")

    async def close_futures_short_order(self, exchange_id: str, symbol: str, amount: float,
                                        leverage=1):
        """
        Đóng lệnh Short futures (async).

        Args:
            exchange_id (str): ID sàn giao dịch
            symbol (str): Ký hiệu cặp giao dịch
            amount (float): Số lượng
            leverage (int): Đòn bẩy

        Returns:
            dict: Thông tin lệnh
        """
        try:
            if not symbol.endswith(':USDT'):
                symbol = f"{extract_base_asset(symbol)}:USDT"
            params = {'leverage': leverage}
            order = await self.exchange_service.async_create_futures_order(
                exchange_id, symbol, 'market', 'buy', amount, params
            )
            log_info(
                f"Đã đóng lệnh short async trên {exchange_id} cho {amount} "
                f"{extract_base_asset(symbol)} với đòn bẩy {leverage}x"
            )
            return order
        except Exception as e:
            raise FuturesError(exchange_id, f"Async: Không thể đóng lệnh short: {str(e)}")

    async def wait_for_futures_order_fill(self, exchange_id: str, symbol: str, timeout: int = 120) -> bool:
        """
        Đợi lệnh futures khớp (async).

        Args:
            exchange_id (str): ID sàn giao dịch
            symbol (str): Ký hiệu cặp giao dịch
            timeout (int): Thời gian chờ tối đa (giây)

        Returns:
            bool: True nếu lệnh đã khớp
        """
        try:
            if not symbol.endswith(':USDT'):
                symbol = f"{extract_base_asset(symbol)}:USDT"

            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < timeout:
                open_orders = await self.exchange_service.async_fetch_open_orders(
                    exchange_id, symbol
                )
                if not open_orders:
                    log_info(f"Lệnh Futures trên {exchange_id} đã được điền.")
                    return True
                await asyncio.sleep(1)

            # Hết thời gian - hủy lệnh còn lại
            open_orders = await self.exchange_service.async_fetch_open_orders(
                exchange_id, symbol
            )
            if open_orders:
                order_id = open_orders[0]['id']
                await self.exchange_service.async_cancel_order(
                    exchange_id, order_id, symbol
                )
                raise OrderFillTimeoutError(exchange_id, order_id, timeout)

            return True

        except OrderFillTimeoutError:
            raise
        except Exception as e:
            raise FuturesError(
                exchange_id,
                f"Lỗi khi đợi lệnh futures khớp: {str(e)}"
            )

    # ─── Position Recovery Helpers ────────────────────────────────────

    async def _emergency_reverse_buy(self, exchange_id: str, symbol: str, amount: float,
                                      notification_service=None) -> None:
        """
        Khi sell thất bại sau khi buy đã đặt: hủy lệnh mua nếu còn open,
        hoặc bán market ngay nếu đã fill để đảo vị thế.
        """
        try:
            open_orders = await self.exchange_service.async_fetch_open_orders(exchange_id, symbol)
            if open_orders:
                await self.exchange_service.async_cancel_order(
                    exchange_id, open_orders[0]['id'], symbol
                )
                log_info(f"Đã hủy lệnh mua trên {exchange_id} (sell thất bại).")
            else:
                await self.exchange_service.async_create_market_sell_order(
                    exchange_id, symbol, amount
                )
                log_warning(f"Lệnh mua đã fill — đã bán market trên {exchange_id} để đảo vị thế.")
            if notification_service:
                notification_service.send_message(
                    f"⚠️ Đảo lệnh mua trên {exchange_id} — sell leg thất bại"
                )
        except Exception as e:
            log_error(f"Lỗi khi đảo lệnh mua trên {exchange_id}: {str(e)}")

    async def _emergency_reverse_sell(self, exchange_id: str, symbol: str, amount: float,
                                       notification_service=None) -> None:
        """
        Khi buy thất bại sau khi sell đã đặt: hủy lệnh bán nếu còn open,
        hoặc mua market ngay nếu đã fill để đảo vị thế.
        """
        try:
            open_orders = await self.exchange_service.async_fetch_open_orders(exchange_id, symbol)
            if open_orders:
                await self.exchange_service.async_cancel_order(
                    exchange_id, open_orders[0]['id'], symbol
                )
                log_info(f"Đã hủy lệnh bán trên {exchange_id} (buy thất bại).")
            else:
                await self.exchange_service.async_create_market_buy_order(
                    exchange_id, symbol, amount
                )
                log_warning(f"Lệnh bán đã fill — đã mua market trên {exchange_id} để đảo vị thế.")
            if notification_service:
                notification_service.send_message(
                    f"⚠️ Đảo lệnh bán trên {exchange_id} — buy leg thất bại"
                )
        except Exception as e:
            log_error(f"Lỗi khi đảo lệnh bán trên {exchange_id}: {str(e)}")

    # ─── Slippage Helpers ─────────────────────────────────────────────

    @staticmethod
    def _extract_fill_price(order_response: Any, expected_price: float) -> float:
        """
        Trích xuất giá fill thực tế từ response của sàn.

        ccxt order response thường có:
        - 'average': giá trung bình fill
        - 'price': giá đặt lệnh
        - 'filled': số lượng đã fill

        Args:
            order_response (dict): Response từ sàn
            expected_price (float): Giá kỳ vọng (fallback)

        Returns:
            float: Giá fill thực tế
        """
        if not order_response or not isinstance(order_response, dict):
            return expected_price

        # Ưu tiên 'average' (giá fill trung bình thực tế)
        if order_response.get('average') and order_response['average'] > 0:
            return float(order_response['average'])

        # Fallback: dùng 'price' từ response
        if order_response.get('price') and order_response['price'] > 0:
            return float(order_response['price'])

        return expected_price

    async def _update_fill_prices(self, fill_result: dict[str, Any], min_ask_ex: str, max_bid_ex: str,
                                   symbol, amount):
        """
        Cập nhật giá fill thực tế từ closed orders sau khi lệnh đã khớp.

        Args:
            fill_result (dict): Dict kết quả để cập nhật
            min_ask_ex (str): Sàn mua
            max_bid_ex (str): Sàn bán
            symbol (str): Cặp giao dịch
            amount (float): Số lượng
        """
        try:
            buy_closed, sell_closed = await asyncio.gather(
                self.exchange_service.async_fetch_closed_orders(min_ask_ex, symbol),
                self.exchange_service.async_fetch_closed_orders(max_bid_ex, symbol),
                return_exceptions=True
            )

            if not isinstance(buy_closed, Exception) and buy_closed:
                last_buy = buy_closed[-1]
                actual = self._extract_fill_price(
                    last_buy, fill_result['expected_buy_price']
                )
                fill_result['actual_buy_price'] = actual

            if not isinstance(sell_closed, Exception) and sell_closed:
                last_sell = sell_closed[-1]
                actual = self._extract_fill_price(
                    last_sell, fill_result['expected_sell_price']
                )
                fill_result['actual_sell_price'] = actual

        except Exception as e:
            log_warning(f"Không thể lấy giá fill thực tế: {str(e)}")

    @staticmethod
    def _calculate_slippage(fill_result: dict[str, Any], amount: float) -> dict[str, Any]:
        """
        Tính slippage dựa trên giá kỳ vọng vs giá thực tế.

        Slippage mua > 0 nghĩa là mua đắt hơn kỳ vọng (bất lợi).
        Slippage bán < 0 nghĩa là bán rẻ hơn kỳ vọng (bất lợi).

        Args:
            fill_result (dict): Dict kết quả để cập nhật
            amount (float): Số lượng giao dịch
        """
        expected_buy = fill_result['expected_buy_price']
        expected_sell = fill_result['expected_sell_price']
        actual_buy = fill_result.get('actual_buy_price') or expected_buy
        actual_sell = fill_result.get('actual_sell_price') or expected_sell

        # Slippage mua: (actual - expected) / expected * 100
        # Dương = mua đắt hơn (bất lợi)
        if expected_buy > 0:
            fill_result['buy_slippage_pct'] = ((actual_buy - expected_buy) / expected_buy) * 100
        else:
            fill_result['buy_slippage_pct'] = 0.0

        # Slippage bán: (actual - expected) / expected * 100
        # Âm = bán rẻ hơn (bất lợi)
        if expected_sell > 0:
            fill_result['sell_slippage_pct'] = ((actual_sell - expected_sell) / expected_sell) * 100
        else:
            fill_result['sell_slippage_pct'] = 0.0

        # Tổng slippage USD = cost mua thêm + doanh thu bán mất
        buy_slippage_usd = (actual_buy - expected_buy) * amount
        sell_slippage_usd = (expected_sell - actual_sell) * amount
        fill_result['total_slippage_usd'] = buy_slippage_usd + sell_slippage_usd
