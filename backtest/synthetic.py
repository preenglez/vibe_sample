"""
합성 주가 데이터 생성기

실제 종목을 모사한 파라미터로 기하 브라운 운동(GBM) 기반 OHLCV 데이터를 생성한다.
네트워크 없이 백테스팅 로직을 검증하거나 시뮬레이션할 때 사용한다.

주요 주식 특성 (대략적 연간 수익률 / 변동성):
  성장주(NVDA류)   : drift +40%, vol 55%
  빅테크(AAPL류)  : drift +20%, vol 28%
  변동성 종목(TSLA): drift +25%, vol 70%
  방어주           : drift +8%,  vol 18%
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class StockProfile:
    name: str
    annual_drift: float    # 연간 기대 수익률 (예: 0.20 = 20%)
    annual_vol: float      # 연간 변동성 (예: 0.30 = 30%)
    start_price: float     # 시작 주가


PROFILES: dict[str, StockProfile] = {
    "AAPL":      StockProfile("AAPL",      0.18, 0.28, 185.0),
    "MSFT":      StockProfile("MSFT",      0.20, 0.26, 375.0),
    "NVDA":      StockProfile("NVDA",      0.45, 0.55, 490.0),
    "GOOGL":     StockProfile("GOOGL",     0.16, 0.27, 165.0),
    "AMZN":      StockProfile("AMZN",      0.22, 0.30, 175.0),
    "META":      StockProfile("META",      0.28, 0.35, 490.0),
    "TSLA":      StockProfile("TSLA",      0.15, 0.68, 240.0),
    "005930.KS": StockProfile("삼성전자",  0.10, 0.30, 71000.0),
    "000660.KS": StockProfile("SK하이닉스", 0.20, 0.42, 170000.0),
    "035420.KS": StockProfile("NAVER",    -0.05, 0.35, 195000.0),
    "005380.KS": StockProfile("현대차",    0.12, 0.28, 230000.0),
}


def generate(
    ticker: str,
    days: int = 365,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """
    ticker에 매핑된 프로파일로 일별 OHLCV 생성.
    ticker가 없으면 중간 수준 파라미터로 생성.
    """
    rng = np.random.default_rng(seed if seed is not None else abs(hash(ticker)) % (2**32))

    profile = PROFILES.get(ticker, StockProfile(ticker, 0.12, 0.30, 100.0))
    dt = 1 / 252
    mu = profile.annual_drift
    sigma = profile.annual_vol

    # GBM으로 종가 시계열 생성
    n_trading = days  # 거래일 수 근사치
    z = rng.standard_normal(n_trading)
    log_returns = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * z
    closes = profile.start_price * np.exp(np.cumsum(log_returns))

    # OHLC 생성 (intraday noise 추가)
    daily_range = sigma * np.sqrt(dt) * closes * rng.uniform(0.5, 1.5, n_trading)
    opens  = closes * (1 + rng.uniform(-0.005, 0.005, n_trading))
    highs  = np.maximum(opens, closes) + daily_range * rng.uniform(0.1, 0.5, n_trading)
    lows   = np.minimum(opens, closes) - daily_range * rng.uniform(0.1, 0.5, n_trading)
    volume = rng.integers(1_000_000, 50_000_000, n_trading).astype(float)

    # 거래일 날짜 인덱스 (주말 제외)
    end_date = pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end_date, periods=n_trading)

    df = pd.DataFrame({
        "Open":   opens,
        "High":   highs,
        "Low":    lows,
        "Close":  closes,
        "Volume": volume,
    }, index=dates)

    return df
