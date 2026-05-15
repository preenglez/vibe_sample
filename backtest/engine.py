"""
백테스팅 엔진

한 종목에 대해 매수/매도 시그널을 적용하고 거래 결과를 반환한다.
포지션은 1개 종목 전량 매수/전량 매도 방식(one-at-a-time)으로 단순화.
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np

from .signals import BuySignalConfig, SellSignalConfig, compute_indicators, get_buy_signal, get_sell_signal


@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: Optional[pd.Timestamp]
    entry_price: float
    exit_price: Optional[float]
    shares: float
    pnl: float = 0.0
    pnl_pct: float = 0.0
    hold_days: int = 0


@dataclass
class BacktestResult:
    ticker: str
    trades: list[Trade]
    equity_curve: pd.Series          # 날짜별 평가 자산
    benchmark_curve: pd.Series       # Buy & Hold 기준선
    total_return_pct: float
    benchmark_return_pct: float
    win_rate: float
    num_trades: int
    avg_hold_days: float
    max_drawdown_pct: float
    sharpe_ratio: float
    buy_cfg: BuySignalConfig
    sell_cfg: SellSignalConfig


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak * 100
    return float(dd.min())


def _sharpe(equity: pd.Series, risk_free: float = 0.03) -> float:
    daily_ret = equity.pct_change().dropna()
    excess = daily_ret - risk_free / 252
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(252))


def run_backtest(
    df: pd.DataFrame,
    ticker: str,
    buy_cfg: BuySignalConfig,
    sell_cfg: SellSignalConfig,
    initial_capital: float = 10_000_000,
) -> BacktestResult:
    """
    df : yfinance로 받은 OHLCV DataFrame (인덱스=날짜, 'Close' 컬럼 필요)
    """
    df = df.copy()
    df = compute_indicators(df, buy_cfg, sell_cfg)
    df.dropna(subset=["Close"], inplace=True)

    buy_signals = get_buy_signal(df, buy_cfg)

    cash = initial_capital
    shares = 0.0
    entry_price = 0.0
    entry_date = None
    peak_price = 0.0

    trades: list[Trade] = []
    equity_vals = []

    for date, row in df.iterrows():
        close = float(row["Close"])

        if shares > 0:
            # 매도 시그널 판단 (단일 행 슬라이스)
            row_df = df.loc[[date]]
            sell_sig = get_sell_signal(row_df, sell_cfg, entry_price, peak_price)
            peak_price = max(peak_price, close)

            if sell_sig.iloc[0]:
                pnl = (close - entry_price) * shares
                pnl_pct = (close / entry_price - 1) * 100
                hold_days = (date - entry_date).days
                cash += close * shares
                trades.append(Trade(
                    entry_date=entry_date,
                    exit_date=date,
                    entry_price=entry_price,
                    exit_price=close,
                    shares=shares,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    hold_days=hold_days,
                ))
                shares = 0.0
                entry_price = 0.0
                peak_price = 0.0

        elif buy_signals.loc[date]:
            # 매수
            shares = cash / close
            entry_price = close
            entry_date = date
            peak_price = close
            cash = 0.0

        equity_vals.append(cash + shares * close)

    equity_curve = pd.Series(equity_vals, index=df.index, name="equity")

    # Buy & Hold 기준선
    first_close = float(df["Close"].iloc[0])
    bh_shares = initial_capital / first_close
    benchmark_curve = (df["Close"] * bh_shares).rename("benchmark")

    total_return_pct = (equity_curve.iloc[-1] / initial_capital - 1) * 100
    benchmark_return_pct = (benchmark_curve.iloc[-1] / initial_capital - 1) * 100

    closed_trades = [t for t in trades if t.exit_date is not None]
    win_rate = (sum(1 for t in closed_trades if t.pnl > 0) / len(closed_trades) * 100) if closed_trades else 0.0
    avg_hold_days = np.mean([t.hold_days for t in closed_trades]) if closed_trades else 0.0

    return BacktestResult(
        ticker=ticker,
        trades=trades,
        equity_curve=equity_curve,
        benchmark_curve=benchmark_curve,
        total_return_pct=total_return_pct,
        benchmark_return_pct=benchmark_return_pct,
        win_rate=win_rate,
        num_trades=len(closed_trades),
        avg_hold_days=float(avg_hold_days),
        max_drawdown_pct=_max_drawdown(equity_curve),
        sharpe_ratio=_sharpe(equity_curve),
        buy_cfg=buy_cfg,
        sell_cfg=sell_cfg,
    )
