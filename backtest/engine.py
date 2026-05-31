"""
Backtest Engine - Replay dữ liệu orderbook lịch sử để mô phỏng giao dịch arbitrage.
"""
import time
from collections import defaultdict
from typing import Any, Optional, Union

from backtest.data_recorder import DataRecorder
from configs import EXCHANGE_FEES, PROFIT_CRITERIA_PCT, PROFIT_CRITERIA_USD
from utils.logger import log_info, log_warning


class BacktestResult:
    """
    Kết quả của một lần backtest.
    """

    def __init__(self) -> None:
        self.trades: list[dict[str, Any]] = []
        self.opportunities: list[dict[str, Any]] = []
        self.equity_curve: list[float] = []
        self.config: dict[str, Any] = {}
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> int:
        return len([t for t in self.trades if t['profit_usd'] > 0])

    @property
    def losing_trades(self) -> int:
        return len([t for t in self.trades if t['profit_usd'] <= 0])

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0
        return self.winning_trades / self.total_trades * 100

    @property
    def total_profit_usd(self) -> float:
        return sum(t['profit_usd'] for t in self.trades)

    @property
    def total_profit_pct(self) -> float:
        return sum(t['profit_pct'] for t in self.trades)

    @property
    def max_drawdown_pct(self) -> float:
        if not self.equity_curve:
            return 0
        peak = self.equity_curve[0]
        max_dd = 0
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def sharpe_ratio(self) -> float:
        """Sharpe ratio đơn giản (không risk-free rate)."""
        if len(self.trades) < 2:
            return 0
        profits = [t['profit_pct'] for t in self.trades]
        mean = sum(profits) / len(profits)
        variance = sum((p - mean) ** 2 for p in profits) / len(profits)
        std = variance ** 0.5
        if std == 0:
            return 0
        return mean / std

    @property
    def avg_profit_per_trade_usd(self) -> float:
        if self.total_trades == 0:
            return 0
        return self.total_profit_usd / self.total_trades

    @property
    def best_trade_usd(self) -> float:
        if not self.trades:
            return 0
        return max(t['profit_usd'] for t in self.trades)

    @property
    def worst_trade_usd(self) -> float:
        if not self.trades:
            return 0
        return min(t['profit_usd'] for t in self.trades)

    @property
    def total_fees_usd(self) -> float:
        return sum(t['fee_usd'] for t in self.trades)

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t['profit_usd'] for t in self.trades if t['profit_usd'] > 0)
        gross_loss = abs(sum(t['profit_usd'] for t in self.trades if t['profit_usd'] < 0))
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0
        return gross_profit / gross_loss

    def summary(self) -> dict[str, Any]:
        """
        Tạo tóm tắt kết quả backtest.

        Returns:
            dict: Tóm tắt kết quả
        """
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate, 2),
            'total_profit_usd': round(self.total_profit_usd, 4),
            'total_profit_pct': round(self.total_profit_pct, 4),
            'avg_profit_per_trade_usd': round(self.avg_profit_per_trade_usd, 4),
            'best_trade_usd': round(self.best_trade_usd, 4),
            'worst_trade_usd': round(self.worst_trade_usd, 4),
            'total_fees_usd': round(self.total_fees_usd, 4),
            'max_drawdown_pct': round(self.max_drawdown_pct, 4),
            'sharpe_ratio': round(self.sharpe_ratio, 4),
            'profit_factor': round(self.profit_factor, 4) if self.profit_factor != float('inf') else 'inf',
            'total_opportunities': len(self.opportunities),
            'config': self.config,
        }


class BacktestEngine:
    """
    Engine chạy backtest trên dữ liệu orderbook lịch sử.
    """

    def __init__(self, data_recorder: Optional[DataRecorder] = None) -> None:
        """
        Khởi tạo backtest engine.

        Args:
            data_recorder (DataRecorder, optional): Data recorder chứa dữ liệu.
        """
        self.data_recorder = data_recorder or DataRecorder()

    def run(self, symbol: str, exchanges: list[str], initial_balance_usd: float = 1000,
            fee_config=None, profit_threshold_usd=None, profit_threshold_pct=None,
            slippage_bps=0, cooldown_seconds=0, start_time=None, end_time=None):
        """
        Chạy backtest.

        Args:
            symbol (str): Cặp giao dịch
            exchanges (list): Danh sách sàn
            initial_balance_usd (float): Số dư ban đầu (USDT)
            fee_config (dict, optional): Cấu hình phí theo sàn
            profit_threshold_usd (float, optional): Ngưỡng lợi nhuận USD
            profit_threshold_pct (float, optional): Ngưỡng lợi nhuận %
            slippage_bps (float): Slippage giả lập (basis points)
            cooldown_seconds (float): Thời gian nghỉ giữa các giao dịch
            start_time (float, optional): Thời gian bắt đầu
            end_time (float, optional): Thời gian kết thúc

        Returns:
            BacktestResult: Kết quả backtest
        """
        fees = fee_config or EXCHANGE_FEES
        min_profit_usd = profit_threshold_usd if profit_threshold_usd is not None else float(PROFIT_CRITERIA_USD)
        min_profit_pct = profit_threshold_pct if profit_threshold_pct is not None else float(PROFIT_CRITERIA_PCT)

        # Lấy dữ liệu
        snapshots = self.data_recorder.get_snapshots(
            symbol, exchanges, start_time, end_time
        )

        if not snapshots:
            log_warning(f"Không có dữ liệu cho {symbol} trên {exchanges}")
            result = BacktestResult()
            result.config = self._build_config(
                symbol, exchanges, initial_balance_usd, fees,
                min_profit_usd, min_profit_pct, slippage_bps, cooldown_seconds
            )
            return result

        # Chuẩn bị state
        result = BacktestResult()
        result.config = self._build_config(
            symbol, exchanges, initial_balance_usd, fees,
            min_profit_usd, min_profit_pct, slippage_bps, cooldown_seconds
        )

        # Phân bổ số dư đều cho các sàn
        balance_per_exchange = initial_balance_usd / len(exchanges)
        usd_balances = {ex: balance_per_exchange for ex in exchanges}
        crypto_balances = {ex: 0.0 for ex in exchanges}

        # Mua crypto ban đầu trên tất cả sàn trừ sàn đầu
        # (Để mô phỏng bot thực: cần có crypto trên sàn bán)
        # Giả lập: mua 50% USDT thành crypto ở mỗi sàn
        first_prices = {}
        for snap in snapshots:
            ex = snap['exchange']
            if ex not in first_prices:
                first_prices[ex] = snap['best_ask']
            if len(first_prices) == len(exchanges):
                break

        for ex in exchanges:
            if ex in first_prices and first_prices[ex] > 0:
                buy_usd = usd_balances[ex] * 0.4
                crypto_balances[ex] = buy_usd / first_prices[ex]
                usd_balances[ex] -= buy_usd

        current_prices = {}  # {exchange: {'bid': x, 'ask': x}}
        last_trade_time = 0
        trade_number = 0

        # Record initial equity
        total_equity = self._calculate_equity(usd_balances, crypto_balances, first_prices)
        result.equity_curve.append(total_equity)
        result.start_time = snapshots[0]['timestamp']
        result.end_time = snapshots[-1]['timestamp']

        # Group snapshots by timestamp
        grouped = self._group_by_timestamp(snapshots)

        for ts, group in grouped.items():
            # Cập nhật giá
            for snap in group:
                ex = snap['exchange']
                current_prices[ex] = {
                    'bid': snap['best_bid'],
                    'ask': snap['best_ask'],
                    'bid_volume': snap.get('bid_volume', 0),
                    'ask_volume': snap.get('ask_volume', 0),
                }

            # Cần giá của tất cả sàn
            if len(current_prices) < len(exchanges):
                continue

            # Tìm cơ hội arbitrage
            min_ask_ex = min(
                exchanges,
                key=lambda ex: current_prices[ex]['ask']
            )
            max_bid_ex = max(
                exchanges,
                key=lambda ex: current_prices[ex]['bid']
            )

            if min_ask_ex == max_bid_ex:
                continue

            buy_price = current_prices[min_ask_ex]['ask']
            sell_price = current_prices[max_bid_ex]['bid']

            if buy_price <= 0:
                continue

            spread_pct = (sell_price - buy_price) / buy_price * 100

            # Tính phí
            fee_buy_rate = fees.get(min_ask_ex, {}).get('give', 0.001)
            fee_sell_rate = fees.get(max_bid_ex, {}).get('receive', 0.001)

            # Tính crypto amount dựa trên balance (giữ lại 2% buffer)
            max_buy_crypto = (usd_balances[min_ask_ex] * 0.98) / buy_price if buy_price > 0 else 0
            max_sell_crypto = crypto_balances[max_bid_ex] * 0.98
            crypto_amount = min(max_buy_crypto, max_sell_crypto)

            if crypto_amount <= 0:
                continue

            # Apply slippage
            actual_buy_price = buy_price * (1 + slippage_bps / 10000)
            actual_sell_price = sell_price * (1 - slippage_bps / 10000)

            # Tính lợi nhuận
            buy_cost = crypto_amount * actual_buy_price
            sell_revenue = crypto_amount * actual_sell_price
            fee_buy = buy_cost * fee_buy_rate
            fee_sell = sell_revenue * fee_sell_rate
            total_fee = fee_buy + fee_sell
            profit_usd = sell_revenue - buy_cost - total_fee

            total_usd = sum(usd_balances.values())
            profit_pct = (profit_usd / total_usd * 100) if total_usd > 0 else 0

            # Ghi opportunity
            result.opportunities.append({
                'timestamp': ts,
                'buy_exchange': min_ask_ex,
                'sell_exchange': max_bid_ex,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'spread_pct': spread_pct,
                'estimated_profit_usd': profit_usd,
            })

            # Kiểm tra điều kiện giao dịch
            if profit_usd <= min_profit_usd:
                continue
            if profit_pct <= min_profit_pct:
                continue

            # Cooldown
            if cooldown_seconds > 0 and (ts - last_trade_time) < cooldown_seconds:
                continue

            # Kiểm tra đủ balance
            if usd_balances[min_ask_ex] < buy_cost * 1.001:
                continue
            if crypto_balances[max_bid_ex] < crypto_amount * 1.001:
                continue

            # Thực hiện giao dịch
            trade_number += 1
            usd_balances[min_ask_ex] -= (buy_cost + fee_buy)
            crypto_balances[min_ask_ex] += crypto_amount
            crypto_balances[max_bid_ex] -= crypto_amount
            usd_balances[max_bid_ex] += (sell_revenue - fee_sell)

            last_trade_time = ts

            # Ghi trade
            cumulative_profit_usd = sum(t['profit_usd'] for t in result.trades) + profit_usd
            result.trades.append({
                'trade_number': trade_number,
                'timestamp': ts,
                'buy_exchange': min_ask_ex,
                'sell_exchange': max_bid_ex,
                'buy_price': round(actual_buy_price, 2),
                'sell_price': round(actual_sell_price, 2),
                'amount': round(crypto_amount, 8),
                'profit_usd': round(profit_usd, 4),
                'profit_pct': round(profit_pct, 6),
                'fee_usd': round(total_fee, 4),
                'cumulative_profit_usd': round(cumulative_profit_usd, 4),
            })

            # Cập nhật equity curve
            mid_prices = {ex: (current_prices[ex]['bid'] + current_prices[ex]['ask']) / 2
                          for ex in exchanges}
            equity = self._calculate_equity(usd_balances, crypto_balances, mid_prices)
            result.equity_curve.append(equity)

        return result

    def run_parameter_sweep(self, symbol: str, exchanges: list[str], initial_balance_usd: float = 1000,
                            fee_config=None, slippage_range=None,
                            profit_threshold_range=None, cooldown_range=None):
        """
        Chạy backtest với nhiều bộ tham số khác nhau.

        Args:
            symbol (str): Cặp giao dịch
            exchanges (list): Danh sách sàn
            initial_balance_usd (float): Số dư ban đầu
            fee_config (dict, optional): Cấu hình phí
            slippage_range (list, optional): Danh sách slippage values (bps)
            profit_threshold_range (list, optional): Danh sách ngưỡng lợi nhuận USD
            cooldown_range (list, optional): Danh sách cooldown (seconds)

        Returns:
            list: Danh sách kết quả, mỗi kết quả kèm tham số
        """
        slippage_values = slippage_range or [0]
        profit_values = profit_threshold_range or [0]
        cooldown_values = cooldown_range or [0]

        results = []

        for slippage in slippage_values:
            for profit_thresh in profit_values:
                for cooldown in cooldown_values:
                    result = self.run(
                        symbol=symbol,
                        exchanges=exchanges,
                        initial_balance_usd=initial_balance_usd,
                        fee_config=fee_config,
                        profit_threshold_usd=profit_thresh,
                        slippage_bps=slippage,
                        cooldown_seconds=cooldown,
                    )
                    results.append({
                        'params': {
                            'slippage_bps': slippage,
                            'profit_threshold_usd': profit_thresh,
                            'cooldown_seconds': cooldown,
                        },
                        'result': result,
                        'summary': result.summary(),
                    })

        # Sắp xếp theo lợi nhuận giảm dần
        results.sort(key=lambda x: x['summary']['total_profit_usd'], reverse=True)
        return results

    def _group_by_timestamp(self, snapshots: list[dict[str, Any]]) -> dict[float, list[dict[str, Any]]]:
        """
        Nhóm snapshots theo timestamp.

        Args:
            snapshots (list): Danh sách snapshot

        Returns:
            dict: {timestamp: [snapshots]}
        """
        grouped = defaultdict(list)
        for snap in snapshots:
            grouped[snap['timestamp']].append(snap)
        return dict(sorted(grouped.items()))

    def _calculate_equity(self, usd_balances: dict[str, float], crypto_balances: dict[str, float],
                           prices: dict[str, Any]) -> float:
        """
        Tính tổng equity (USDT).

        Args:
            usd_balances (dict): Số dư USDT mỗi sàn
            crypto_balances (dict): Số dư crypto mỗi sàn
            prices (dict): Giá hiện tại mỗi sàn

        Returns:
            float: Tổng equity
        """
        total = sum(usd_balances.values())
        for ex, crypto in crypto_balances.items():
            if ex in prices:
                price = prices[ex] if isinstance(prices[ex], (int, float)) else prices[ex].get('bid', 0)
                total += crypto * price
        return round(total, 4)

    def _build_config(self, symbol: str, exchanges: list[str], initial_balance_usd: float, fees: dict[str, Any],
                      min_profit_usd, min_profit_pct, slippage_bps, cooldown_seconds):
        """Tạo dict cấu hình cho kết quả."""
        return {
            'symbol': symbol,
            'exchanges': exchanges,
            'initial_balance_usd': initial_balance_usd,
            'fee_config': {k: v for k, v in fees.items() if k in exchanges},
            'profit_threshold_usd': min_profit_usd,
            'profit_threshold_pct': min_profit_pct,
            'slippage_bps': slippage_bps,
            'cooldown_seconds': cooldown_seconds,
        }
