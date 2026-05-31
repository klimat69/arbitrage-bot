"""
Backtest Analyzer - Phân tích và so sánh kết quả backtest.
"""
from typing import Any, Union
from backtest.engine import BacktestResult


class BacktestAnalyzer:
    """
    Phân tích kết quả backtest chi tiết.
    """

    @staticmethod
    def analyze(result: BacktestResult) -> dict[str, Any]:
        """
        Phân tích chi tiết một kết quả backtest.

        Args:
            result (BacktestResult): Kết quả backtest

        Returns:
            dict: Phân tích chi tiết
        """
        summary = result.summary()

        # Phân tích theo cặp sàn
        exchange_pairs = {}
        for trade in result.trades:
            pair = f"{trade['buy_exchange']}->{trade['sell_exchange']}"
            if pair not in exchange_pairs:
                exchange_pairs[pair] = {
                    'count': 0,
                    'total_profit_usd': 0,
                    'total_fee_usd': 0,
                }
            exchange_pairs[pair]['count'] += 1
            exchange_pairs[pair]['total_profit_usd'] += trade['profit_usd']
            exchange_pairs[pair]['total_fee_usd'] += trade['fee_usd']

        # Consecutive wins/losses
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0
        for trade in result.trades:
            if trade['profit_usd'] > 0:
                current_wins += 1
                current_losses = 0
            else:
                current_losses += 1
                current_wins = 0
            max_consecutive_wins = max(max_consecutive_wins, current_wins)
            max_consecutive_losses = max(max_consecutive_losses, current_losses)

        # Thời gian trung bình giữa các trades
        avg_time_between_trades = 0
        if len(result.trades) > 1:
            time_diffs = []
            for i in range(1, len(result.trades)):
                diff = result.trades[i]['timestamp'] - result.trades[i-1]['timestamp']
                time_diffs.append(diff)
            avg_time_between_trades = sum(time_diffs) / len(time_diffs)

        # Opportunity conversion rate
        conversion_rate = 0
        if len(result.opportunities) > 0:
            conversion_rate = result.total_trades / len(result.opportunities) * 100

        return {
            **summary,
            'exchange_pairs': exchange_pairs,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'avg_time_between_trades_sec': round(avg_time_between_trades, 2),
            'opportunity_conversion_rate': round(conversion_rate, 2),
            'total_opportunities': len(result.opportunities),
        }

    @staticmethod
    def compare(results: list[Union[BacktestResult, dict[str, Any]]]) -> list[dict[str, Any]]:
        """
        So sánh nhiều kết quả backtest.

        Args:
            results (list): Danh sách BacktestResult hoặc sweep results

        Returns:
            list: Danh sách tóm tắt đã sắp xếp theo lợi nhuận
        """
        comparisons = []
        for i, r in enumerate(results):
            if isinstance(r, dict) and 'result' in r:
                # Sweep result format
                summary = r['summary']
                summary['params'] = r['params']
            elif isinstance(r, BacktestResult):
                summary = r.summary()
            else:
                continue

            summary['rank'] = i + 1
            comparisons.append(summary)

        comparisons.sort(key=lambda x: x['total_profit_usd'], reverse=True)
        for i, c in enumerate(comparisons):
            c['rank'] = i + 1

        return comparisons

    @staticmethod
    def format_report(result: BacktestResult) -> str:
        """
        Tạo báo cáo text cho kết quả backtest.

        Args:
            result (BacktestResult): Kết quả backtest

        Returns:
            str: Báo cáo dạng text
        """
        analysis = BacktestAnalyzer.analyze(result)

        lines = [
            "=" * 60,
            "BÁO CÁO BACKTEST ARBITRAGE",
            "=" * 60,
            "",
            f"Symbol: {analysis['config'].get('symbol', 'N/A')}",
            f"Sàn: {', '.join(analysis['config'].get('exchanges', []))}",
            f"Số dư ban đầu: {analysis['config'].get('initial_balance_usd', 0)} USDT",
            f"Slippage: {analysis['config'].get('slippage_bps', 0)} bps",
            "",
            "-" * 40,
            "KẾT QUẢ GIAO DỊCH",
            "-" * 40,
            f"Tổng giao dịch: {analysis['total_trades']}",
            f"  Thắng: {analysis['winning_trades']}",
            f"  Thua: {analysis['losing_trades']}",
            f"  Tỷ lệ thắng: {analysis['win_rate']}%",
            "",
            f"Tổng lợi nhuận: {analysis['total_profit_usd']} USDT ({analysis['total_profit_pct']}%)",
            f"  TB mỗi giao dịch: {analysis['avg_profit_per_trade_usd']} USDT",
            f"  Tốt nhất: {analysis['best_trade_usd']} USDT",
            f"  Tệ nhất: {analysis['worst_trade_usd']} USDT",
            "",
            f"Tổng phí: {analysis['total_fees_usd']} USDT",
            f"Max Drawdown: {analysis['max_drawdown_pct']}%",
            f"Sharpe Ratio: {analysis['sharpe_ratio']}",
            f"Profit Factor: {analysis['profit_factor']}",
            "",
            f"Chuỗi thắng dài nhất: {analysis['max_consecutive_wins']}",
            f"Chuỗi thua dài nhất: {analysis['max_consecutive_losses']}",
            f"TB thời gian giữa trades: {analysis['avg_time_between_trades_sec']}s",
            "",
            f"Cơ hội phát hiện: {analysis['total_opportunities']}",
            f"Tỷ lệ chuyển đổi: {analysis['opportunity_conversion_rate']}%",
        ]

        # Phân tích theo cặp sàn
        if analysis.get('exchange_pairs'):
            lines.append("")
            lines.append("-" * 40)
            lines.append("PHÂN TÍCH THEO CẶP SÀN")
            lines.append("-" * 40)
            for pair, stats in analysis['exchange_pairs'].items():
                lines.append(
                    f"  {pair}: {stats['count']} trades, "
                    f"lợi nhuận: {round(stats['total_profit_usd'], 4)} USDT, "
                    f"phí: {round(stats['total_fee_usd'], 4)} USDT"
                )

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)
