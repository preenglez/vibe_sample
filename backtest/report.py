"""결과 출력 및 차트 저장"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from tabulate import tabulate

from .engine import BacktestResult


def print_summary(results: list[BacktestResult]) -> None:
    rows = []
    for r in results:
        rows.append([
            r.ticker,
            r.buy_cfg.describe(),
            r.sell_cfg.describe(),
            f"{r.total_return_pct:+.1f}%",
            f"{r.benchmark_return_pct:+.1f}%",
            f"{r.total_return_pct - r.benchmark_return_pct:+.1f}%",
            f"{r.win_rate:.0f}%",
            r.num_trades,
            f"{r.avg_hold_days:.0f}일",
            f"{r.max_drawdown_pct:.1f}%",
            f"{r.sharpe_ratio:.2f}",
        ])

    headers = [
        "종목", "매수 시그널", "매도 시그널",
        "전략 수익률", "B&H 수익률", "초과수익",
        "승률", "거래수", "평균보유", "최대낙폭", "샤프"
    ]
    print("\n" + "=" * 120)
    print("  백테스팅 결과 요약")
    print("=" * 120)
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline", numalign="right"))


def print_trades(result: BacktestResult, max_rows: int = 20) -> None:
    if not result.trades:
        print(f"\n[{result.ticker}] 거래 없음")
        return

    rows = []
    for t in result.trades[:max_rows]:
        exit_date = t.exit_date.strftime("%Y-%m-%d") if t.exit_date else "보유중"
        exit_price = f"{t.exit_price:,.0f}" if t.exit_price else "-"
        rows.append([
            t.entry_date.strftime("%Y-%m-%d"),
            exit_date,
            f"{t.entry_price:,.0f}",
            exit_price,
            f"{t.pnl_pct:+.1f}%" if t.exit_price else "-",
            f"{t.hold_days}일",
        ])

    print(f"\n[{result.ticker}] 거래 내역 (최근 {min(max_rows, len(result.trades))}건)")
    print(tabulate(rows,
                   headers=["매수일", "매도일", "매수가", "매도가", "수익률", "보유기간"],
                   tablefmt="simple"))


def save_chart(results: list[BacktestResult], output_dir: str = "backtest_output") -> None:
    os.makedirs(output_dir, exist_ok=True)

    # 종목별 차트
    for r in results:
        fig, axes = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [3, 1]})
        fig.suptitle(f"{r.ticker}  |  {r.buy_cfg.describe()} / {r.sell_cfg.describe()}", fontsize=12)

        ax1 = axes[0]
        ax1.plot(r.equity_curve.index, r.equity_curve.values, label="전략", color="#2196F3", linewidth=1.8)
        ax1.plot(r.benchmark_curve.index, r.benchmark_curve.values,
                 label="Buy & Hold", color="#9E9E9E", linewidth=1.2, linestyle="--")

        # 거래 마커
        for t in r.trades:
            ax1.axvline(t.entry_date, color="#4CAF50", alpha=0.4, linewidth=0.8)
            if t.exit_date:
                ax1.axvline(t.exit_date, color="#F44336", alpha=0.4, linewidth=0.8)

        ax1.set_ylabel("평가 자산 (원)")
        ax1.legend(loc="upper left")
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
        ax1.grid(alpha=0.3)

        # 수익률 바
        ax2 = axes[1]
        pnls = [t.pnl_pct for t in r.trades if t.exit_date]
        colors = ["#4CAF50" if p > 0 else "#F44336" for p in pnls]
        ax2.bar(range(len(pnls)), pnls, color=colors)
        ax2.axhline(0, color="black", linewidth=0.8)
        ax2.set_xlabel("거래 번호")
        ax2.set_ylabel("수익률 (%)")
        ax2.grid(alpha=0.3)

        plt.tight_layout()
        path = os.path.join(output_dir, f"{r.ticker.replace('.', '_')}.png")
        plt.savefig(path, dpi=120, bbox_inches="tight")
        plt.close()
        print(f"  차트 저장: {path}")

    # 종합 수익률 비교 차트
    if len(results) > 1:
        fig, ax = plt.subplots(figsize=(14, 6))
        for r in results:
            norm = r.equity_curve / r.equity_curve.iloc[0] * 100
            ax.plot(norm.index, norm.values, label=r.ticker, linewidth=1.5)

        ax.axhline(100, color="black", linewidth=0.8, linestyle="--")
        ax.set_title("종목별 전략 수익률 비교 (기준=100)")
        ax.set_ylabel("수익률 지수")
        ax.legend(loc="upper left", ncol=3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
        ax.grid(alpha=0.3)
        plt.tight_layout()
        path = os.path.join(output_dir, "comparison.png")
        plt.savefig(path, dpi=120, bbox_inches="tight")
        plt.close()
        print(f"  차트 저장: {path}")
