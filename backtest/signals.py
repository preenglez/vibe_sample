"""
매수/매도 시그널 정의

매수 시그널 (무릎 감지 - 상승 시작 포착):
  - golden_cross : 단기 MA가 장기 MA를 상향 돌파
  - rsi_recovery : RSI가 과매도 구간에서 회복
  - macd_cross   : MACD선이 시그널선을 상향 돌파

매도 시그널 (어깨 감지 - 하락 시작 포착):
  - trailing_stop : 최고가 대비 N% 하락
  - ma_break      : 종가가 이동평균선 아래로 하락
  - death_cross   : 단기 MA가 장기 MA를 하향 돌파
"""

from dataclasses import dataclass, field
from typing import Literal
import pandas as pd
import numpy as np


@dataclass
class BuySignalConfig:
    signal_type: Literal["golden_cross", "rsi_recovery", "macd_cross"] = "golden_cross"

    # golden_cross 파라미터
    short_ma: int = 5
    long_ma: int = 20

    # rsi_recovery 파라미터
    rsi_period: int = 14
    rsi_buy_threshold: float = 35.0   # RSI가 이 값을 상향 돌파할 때 매수

    # macd_cross 파라미터
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    def describe(self) -> str:
        if self.signal_type == "golden_cross":
            return f"골든크로스 (MA{self.short_ma}/MA{self.long_ma})"
        elif self.signal_type == "rsi_recovery":
            return f"RSI 회복 (RSI{self.rsi_period} > {self.rsi_buy_threshold})"
        elif self.signal_type == "macd_cross":
            return f"MACD 크로스 ({self.macd_fast}/{self.macd_slow}/{self.macd_signal})"
        return self.signal_type


@dataclass
class SellSignalConfig:
    signal_type: Literal["trailing_stop", "ma_break", "death_cross"] = "trailing_stop"

    # trailing_stop 파라미터
    trailing_stop_pct: float = 8.0    # 최고가 대비 N% 하락시 매도

    # ma_break 파라미터
    ma_break_period: int = 20

    # death_cross 파라미터
    short_ma: int = 5
    long_ma: int = 20

    def describe(self) -> str:
        if self.signal_type == "trailing_stop":
            return f"트레일링스탑 ({self.trailing_stop_pct}% 하락)"
        elif self.signal_type == "ma_break":
            return f"MA 이탈 (MA{self.ma_break_period} 하향돌파)"
        elif self.signal_type == "death_cross":
            return f"데드크로스 (MA{self.short_ma}/MA{self.long_ma})"
        return self.signal_type


def compute_indicators(df: pd.DataFrame, buy_cfg: BuySignalConfig, sell_cfg: SellSignalConfig) -> pd.DataFrame:
    """필요한 지표를 모두 계산해서 df에 컬럼으로 추가"""
    close = df["Close"]

    # --- 이동평균 ---
    ma_periods = set()
    if buy_cfg.signal_type == "golden_cross":
        ma_periods.update([buy_cfg.short_ma, buy_cfg.long_ma])
    if sell_cfg.signal_type in ("ma_break", "death_cross"):
        if sell_cfg.signal_type == "ma_break":
            ma_periods.add(sell_cfg.ma_break_period)
        else:
            ma_periods.update([sell_cfg.short_ma, sell_cfg.long_ma])

    for p in ma_periods:
        df[f"MA{p}"] = close.rolling(p).mean()

    # --- RSI ---
    if buy_cfg.signal_type == "rsi_recovery":
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(buy_cfg.rsi_period).mean()
        loss = (-delta.clip(upper=0)).rolling(buy_cfg.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        df["RSI"] = 100 - 100 / (1 + rs)

    # --- MACD ---
    if buy_cfg.signal_type == "macd_cross":
        ema_fast = close.ewm(span=buy_cfg.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=buy_cfg.macd_slow, adjust=False).mean()
        df["MACD"] = ema_fast - ema_slow
        df["MACD_signal"] = df["MACD"].ewm(span=buy_cfg.macd_signal, adjust=False).mean()
        df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

    return df


def get_buy_signal(df: pd.DataFrame, cfg: BuySignalConfig) -> pd.Series:
    """매수 시그널: True인 날에 매수"""
    idx = df.index

    if cfg.signal_type == "golden_cross":
        short = df[f"MA{cfg.short_ma}"]
        long_ = df[f"MA{cfg.long_ma}"]
        cross = (short > long_) & (short.shift(1) <= long_.shift(1))
        return cross.fillna(False)

    elif cfg.signal_type == "rsi_recovery":
        rsi = df["RSI"]
        # 전날 RSI < threshold, 오늘 RSI >= threshold (상향 돌파)
        cross = (rsi >= cfg.rsi_buy_threshold) & (rsi.shift(1) < cfg.rsi_buy_threshold)
        return cross.fillna(False)

    elif cfg.signal_type == "macd_cross":
        hist = df["MACD_hist"]
        # MACD 히스토그램이 음에서 양으로 전환
        cross = (hist > 0) & (hist.shift(1) <= 0)
        return cross.fillna(False)

    return pd.Series(False, index=idx)


def get_sell_signal(df: pd.DataFrame, cfg: SellSignalConfig, entry_price: float, peak_price: float) -> pd.Series:
    """
    매도 시그널: True인 날에 매도
    entry_price : 매수 가격
    peak_price  : 보유 기간 중 최고 종가 (트레일링스탑용, 외부에서 누적 갱신)
    """
    idx = df.index

    if cfg.signal_type == "trailing_stop":
        stop = peak_price * (1 - cfg.trailing_stop_pct / 100)
        return (df["Close"] <= stop).fillna(False)

    elif cfg.signal_type == "ma_break":
        ma = df[f"MA{cfg.ma_break_period}"]
        # 전날 종가 >= MA, 오늘 종가 < MA (이탈)
        break_down = (df["Close"] < ma) & (df["Close"].shift(1) >= ma.shift(1))
        return break_down.fillna(False)

    elif cfg.signal_type == "death_cross":
        short = df[f"MA{cfg.short_ma}"]
        long_ = df[f"MA{cfg.long_ma}"]
        cross = (short < long_) & (short.shift(1) >= long_.shift(1))
        return cross.fillna(False)

    return pd.Series(False, index=idx)
