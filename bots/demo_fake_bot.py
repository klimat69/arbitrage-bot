#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script demo chạy FakeMoneyBot với dữ liệu thực từ các sàn.
Không cần API keys - chỉ dùng public orderbook data.

Cách chạy:
    python -m bots.demo_fake_bot
    python -m bots.demo_fake_bot --symbol ETH/USDT --duration 2
    python -m bots.demo_fake_bot --exchanges binance bybit --symbol BTC/USDT
"""
import asyncio
import argparse
import os
import time
import sys
from colorama import Fore, Style, init
import ccxt.pro

# Thêm project root vào sys.path để import configs
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configs import EXCHANGE_FEES

init()

# ─── Config ────────────────────────────────────────────────────

DEFAULT_SYMBOL = "BTC/USDT"
DEFAULT_EXCHANGES = ["binance", "okx", "bybit"]
DEFAULT_DURATION_MIN = 1
DEFAULT_USD = 1000.0


# ─── FakeMoneyDemo ─────────────────────────────────────────────

class FakeMoneyDemo:
    """Demo bot mô phỏng giao dịch arbitrage với dữ liệu orderbook thực."""

    def __init__(self, symbol: str, exchanges: list, usd_amount: float, duration_min: int):
        self.symbol = symbol
        self.exchange_ids = exchanges
        self.usd_amount = usd_amount
        self.duration_sec = duration_min * 60
        self.orderbooks = {}
        self.pro_exchanges = {}

        # Fake balances
        self.initial_usd = usd_amount
        self.total_profit_usd = 0.0
        self.trade_count = 0
        self.opportunities = 0

    async def run(self):
        """Chạy demo bot."""
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}  BMLB FAKE MONEY DEMO - Dữ liệu thực từ sàn{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"  Symbol  : {Fore.YELLOW}{self.symbol}{Style.RESET_ALL}")
        print(f"  Sàn     : {Fore.YELLOW}{', '.join(self.exchange_ids)}{Style.RESET_ALL}")
        print(f"  Vốn     : {Fore.GREEN}{self.usd_amount} USDT{Style.RESET_ALL}")
        print(f"  Thời gian: {Fore.YELLOW}{self.duration_sec // 60} phút{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

        # Khởi tạo exchanges (public, không cần API key)
        for eid in self.exchange_ids:
            try:
                exchange_class = getattr(ccxt.pro, eid)
                self.pro_exchanges[eid] = exchange_class({'enableRateLimit': True})
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Kết nối {eid}")
            except Exception as e:
                print(f"  {Fore.RED}✗{Style.RESET_ALL} Không thể kết nối {eid}: {e}")

        if len(self.pro_exchanges) < 2:
            print(f"\n{Fore.RED}Cần ít nhất 2 sàn để chạy arbitrage!{Style.RESET_ALL}")
            return

        print(f"\n{Fore.YELLOW}Đang theo dõi orderbook... (Ctrl+C để dừng){Style.RESET_ALL}\n")

        timeout = time.time() + self.duration_sec

        try:
            # Chạy song song các vòng lặp orderbook
            tasks = [self._watch_orderbook(eid, timeout) for eid in self.pro_exchanges]
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Đã dừng bởi người dùng.{Style.RESET_ALL}")
        finally:
            # Đóng tất cả connections
            for eid, ex in self.pro_exchanges.items():
                try:
                    await ex.close()
                except Exception:
                    pass

            self._print_summary()

    async def _watch_orderbook(self, exchange_id: str, timeout: float):
        """Theo dõi orderbook của một sàn và phát hiện cơ hội arbitrage."""
        exchange = self.pro_exchanges[exchange_id]

        while time.time() < timeout:
            try:
                ob = await exchange.watch_order_book(self.symbol)
                if ob['bids'] and ob['asks']:
                    self.orderbooks[exchange_id] = {
                        'bid': ob['bids'][0][0],
                        'ask': ob['asks'][0][0],
                        'bid_vol': ob['bids'][0][1],
                        'ask_vol': ob['asks'][0][1],
                        'time': time.time()
                    }
                    # Kiểm tra cơ hội arbitrage mỗi khi có dữ liệu mới
                    self._check_arbitrage(exchange_id)

            except Exception as e:
                err_str = str(e)
                if 'ExchangeClosedByUser' in err_str or 'connection closed' in err_str.lower():
                    break
                print(f"  {Fore.RED}[{exchange_id}] Lỗi: {err_str[:80]}{Style.RESET_ALL}")
                await asyncio.sleep(1)

    def _check_arbitrage(self, trigger_exchange: str):
        """Kiểm tra cơ hội arbitrage giữa các sàn."""
        if len(self.orderbooks) < 2:
            return

        # Chỉ kiểm tra nếu tất cả data < 5 giây
        now = time.time()
        fresh = {k: v for k, v in self.orderbooks.items() if now - v['time'] < 5}
        if len(fresh) < 2:
            return

        # Tìm sàn có ask thấp nhất (mua) và bid cao nhất (bán)
        best_ask_exchange = min(fresh, key=lambda k: fresh[k]['ask'])
        best_bid_exchange = max(fresh, key=lambda k: fresh[k]['bid'])

        if best_ask_exchange == best_bid_exchange:
            return

        ask_price = fresh[best_ask_exchange]['ask']
        bid_price = fresh[best_bid_exchange]['bid']
        spread_pct = ((bid_price - ask_price) / ask_price) * 100

        # Tính phí
        buy_fee = EXCHANGE_FEES.get(best_ask_exchange, {'give': 0.001})['give']
        sell_fee = EXCHANGE_FEES.get(best_bid_exchange, {'receive': 0.001})['receive']
        total_fee_pct = (buy_fee + sell_fee) * 100

        net_profit_pct = spread_pct - total_fee_pct

        self.opportunities += 1

        # Hiển thị mỗi cơ hội
        timestamp = time.strftime('%H:%M:%S')

        if net_profit_pct > 0:
            # Cơ hội có lãi — mô phỏng giao dịch
            trade_amount = self.usd_amount * 0.1  # Dùng 10% vốn mỗi lệnh
            crypto_amount = trade_amount / ask_price
            profit_usd = crypto_amount * (bid_price - ask_price) - (trade_amount * (buy_fee + sell_fee))

            self.total_profit_usd += profit_usd
            self.trade_count += 1

            print(
                f"  {Fore.GREEN}[{timestamp}] ★ TRADE #{self.trade_count}{Style.RESET_ALL} | "
                f"Mua {best_ask_exchange} @ {ask_price:,.2f} → "
                f"Bán {best_bid_exchange} @ {bid_price:,.2f} | "
                f"Spread: {Fore.GREEN}{spread_pct:+.4f}%{Style.RESET_ALL} | "
                f"Net: {Fore.GREEN}{net_profit_pct:+.4f}%{Style.RESET_ALL} | "
                f"P&L: {Fore.GREEN}+{profit_usd:.4f} USD{Style.RESET_ALL}"
            )
        else:
            # Cơ hội không đủ lãi — chỉ log
            if self.opportunities % 50 == 0:  # In mỗi 50 lần để không spam
                print(
                    f"  {Fore.WHITE}[{timestamp}]{Style.RESET_ALL} "
                    f"Mua {best_ask_exchange} @ {ask_price:,.2f} → "
                    f"Bán {best_bid_exchange} @ {bid_price:,.2f} | "
                    f"Spread: {Fore.RED}{spread_pct:+.4f}%{Style.RESET_ALL} | "
                    f"Net: {Fore.RED}{net_profit_pct:+.4f}%{Style.RESET_ALL} (chưa đủ lãi)"
                )

    def _print_summary(self):
        """In tổng kết phiên giao dịch."""
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}  KẾT QUẢ PHIÊN MÔ PHỎNG{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"  Cặp giao dịch  : {self.symbol}")
        print(f"  Sàn            : {', '.join(self.exchange_ids)}")
        print(f"  Vốn ban đầu    : {self.initial_usd:,.2f} USDT")
        print(f"  Cơ hội phát hiện: {self.opportunities}")
        print(f"  Giao dịch thực hiện: {self.trade_count}")

        color = Fore.GREEN if self.total_profit_usd >= 0 else Fore.RED
        profit_pct = (self.total_profit_usd / self.initial_usd * 100) if self.initial_usd else 0
        print(f"  Lợi nhuận      : {color}{self.total_profit_usd:+.4f} USD ({profit_pct:+.4f}%){Style.RESET_ALL}")
        print(f"  Vốn cuối       : {self.initial_usd + self.total_profit_usd:,.2f} USDT")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


# ─── Main ──────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description='Demo FakeMoneyBot - Dữ liệu thật, tiền giả')
    parser.add_argument('--symbol', default=DEFAULT_SYMBOL, help=f'Cặp giao dịch (mặc định: {DEFAULT_SYMBOL})')
    parser.add_argument('--exchanges', nargs='+', default=DEFAULT_EXCHANGES, help=f'Danh sách sàn (mặc định: {" ".join(DEFAULT_EXCHANGES)})')
    parser.add_argument('--usd', type=float, default=DEFAULT_USD, help=f'Vốn USDT (mặc định: {DEFAULT_USD})')
    parser.add_argument('--duration', type=int, default=DEFAULT_DURATION_MIN, help=f'Thời gian chạy (phút, mặc định: {DEFAULT_DURATION_MIN})')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    demo = FakeMoneyDemo(
        symbol=args.symbol,
        exchanges=args.exchanges,
        usd_amount=args.usd,
        duration_min=args.duration
    )

    try:
        asyncio.run(demo.run())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Đã dừng.{Style.RESET_ALL}")
