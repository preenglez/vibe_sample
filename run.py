"""
백테스팅 실행 진입점  —  무릎에서 사서 어깨에서 판다

사용법:
  python run.py                                      # 기본 설정 (합성 데이터, US 종목)
  python run.py --strategy all                       # 모든 시그널 조합 비교
  python run.py --buy golden_cross --sell trailing_stop --stop 10
  python run.py --buy rsi_recovery --rsi-threshold 30 --sell ma_break --ma 20
  python run.py --buy macd_cross --sell death_cross
  python run.py --market KR                          # 한국 주요 종목
  python run.py --market ALL                         # 미국+한국 전체
  python run.py --tickers AAPL MSFT NVDA             # 종목 직접 지정
  python run.py --real                               # Yahoo Finance 실시간 데이터 시도
  python run.py --no-chart                           # 차트 저장 생략
  python run.py --trades                             # 거래 내역 상세 출력
"""

import argparse
import sys
from datetime import datetime, timedelta

import pandas as pd

from backtest import BuySignalConfig, SellSignalConfig, run_backtest, print_summary, print_trades, save_chart
from backtest.synthetic import generate as generate_synthetic

# ──────────────────────────────────────────────
# 기본 종목 목록
# ──────────────────────────────────────────────
DEFAULT_TICKERS = {
    "US": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"],
    "KR": ["005930.KS", "000660.KS", "035420.KS", "005380.KS"],
}


def fetch_real_data(tickers: list[str], days: int = 365) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    end = datetime.today()
    start = end - timedelta(days=days)
    data = {}
    print(f"\n실시간 데이터 다운로드 ({start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')})")
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
            if df.empty or len(df) < 30:
                print(f"  {ticker}: 데이터 부족, 건너뜀")
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index = pd.to_datetime(df.index)
            data[ticker] = df
            print(f"  {ticker}: {len(df)}거래일 로드 완료")
        except Exception as e:
            print(f"  {ticker}: 다운로드 실패 ({e})")
    return data


def fetch_synthetic_data(tickers: list[str], days: int = 365) -> dict[str, pd.DataFrame]:
    print(f"\n합성 데이터 생성 ({days}거래일, 기하 브라운 운동 모델)")
    data = {}
    for ticker in tickers:
        df = generate_synthetic(ticker, days=days)
        data[ticker] = df
        print(f"  {ticker}: {len(df)}거래일 생성 완료")
    return data


def build_signal_combos() -> list[tuple[BuySignalConfig, SellSignalConfig]]:
    """--strategy all 일 때 테스트할 시그널 조합"""
    buys = [
        BuySignalConfig(signal_type="golden_cross", short_ma=5, long_ma=20),
        BuySignalConfig(signal_type="golden_cross", short_ma=10, long_ma=30),
        BuySignalConfig(signal_type="rsi_recovery", rsi_period=14, rsi_buy_threshold=35),
        BuySignalConfig(signal_type="macd_cross"),
    ]
    sells = [
        SellSignalConfig(signal_type="trailing_stop", trailing_stop_pct=8),
        SellSignalConfig(signal_type="trailing_stop", trailing_stop_pct=12),
        SellSignalConfig(signal_type="ma_break", ma_break_period=20),
        SellSignalConfig(signal_type="death_cross", short_ma=5, long_ma=20),
    ]
    return [(b, s) for b in buys for s in sells]


def parse_args():
    parser = argparse.ArgumentParser(
        description="주식 백테스팅 — 무릎에서 사서 어깨에서 판다",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("--tickers", nargs="+", default=None,
                        help="종목 코드 목록 (기본: US 주요 종목)")
    parser.add_argument("--market", choices=["US", "KR", "ALL"], default="US",
                        help="종목 시장 선택 (기본: US)")
    parser.add_argument("--days", type=int, default=365,
                        help="백테스트 기간 거래일수 (기본: 365)")
    parser.add_argument("--capital", type=float, default=10_000_000,
                        help="초기 자본 (기본: 10,000,000)")
    parser.add_argument("--real", action="store_true",
                        help="Yahoo Finance 실시간 데이터 사용 (기본: 합성 데이터)")

    parser.add_argument("--strategy", choices=["custom", "all"], default="custom",
                        help="'custom': 아래 파라미터 사용 / 'all': 모든 시그널 조합 비교")

    # 매수 시그널
    buy_grp = parser.add_argument_group("매수 시그널")
    buy_grp.add_argument("--buy", choices=["golden_cross", "rsi_recovery", "macd_cross"],
                         default="golden_cross",
                         help="매수 시그널 종류 (기본: golden_cross)")
    buy_grp.add_argument("--short-ma", type=int, default=5,
                         help="단기 이동평균 기간 (기본: 5)")
    buy_grp.add_argument("--long-ma", type=int, default=20,
                         help="장기 이동평균 기간 (기본: 20)")
    buy_grp.add_argument("--rsi-period", type=int, default=14,
                         help="RSI 계산 기간 (기본: 14)")
    buy_grp.add_argument("--rsi-threshold", type=float, default=35.0,
                         help="RSI 매수 임계값 (기본: 35 — 상향 돌파시 매수)")

    # 매도 시그널
    sell_grp = parser.add_argument_group("매도 시그널")
    sell_grp.add_argument("--sell", choices=["trailing_stop", "ma_break", "death_cross"],
                          default="trailing_stop",
                          help="매도 시그널 종류 (기본: trailing_stop)")
    sell_grp.add_argument("--stop", type=float, default=8.0,
                          help="트레일링스탑 하락률 %% (기본: 8)")
    sell_grp.add_argument("--ma", type=int, default=20,
                          help="MA이탈 이동평균 기간 (기본: 20)")

    parser.add_argument("--no-chart", action="store_true", help="차트 저장 생략")
    parser.add_argument("--trades", action="store_true", help="거래 내역 출력")

    return parser.parse_args()


def main():
    args = parse_args()

    # 종목 결정
    if args.tickers:
        tickers = args.tickers
    elif args.market == "ALL":
        tickers = DEFAULT_TICKERS["US"] + DEFAULT_TICKERS["KR"]
    else:
        tickers = DEFAULT_TICKERS[args.market]

    # 데이터 로드
    if args.real:
        data = fetch_real_data(tickers, days=args.days)
    else:
        data = fetch_synthetic_data(tickers, days=args.days)

    if not data:
        print("사용 가능한 데이터가 없습니다.")
        sys.exit(1)

    # 시그널 조합 결정
    if args.strategy == "all":
        combos = build_signal_combos()
        print(f"\n시그널 조합 {len(combos)}가지 × 종목 {len(data)}개 = {len(combos)*len(data)}회 백테스트")
    else:
        buy_cfg = BuySignalConfig(
            signal_type=args.buy,
            short_ma=args.short_ma,
            long_ma=args.long_ma,
            rsi_period=args.rsi_period,
            rsi_buy_threshold=args.rsi_threshold,
        )
        sell_cfg = SellSignalConfig(
            signal_type=args.sell,
            trailing_stop_pct=args.stop,
            ma_break_period=args.ma,
            short_ma=args.short_ma,
            long_ma=args.long_ma,
        )
        combos = [(buy_cfg, sell_cfg)]

    # 백테스트 실행
    all_results = []
    for ticker, df in data.items():
        for buy_cfg, sell_cfg in combos:
            try:
                result = run_backtest(df, ticker, buy_cfg, sell_cfg, initial_capital=args.capital)
                all_results.append(result)
            except Exception as e:
                print(f"  [{ticker}] 백테스트 오류: {e}")

    if not all_results:
        print("실행된 백테스트가 없습니다.")
        sys.exit(1)

    # 결과 출력
    print_summary(all_results)

    if args.trades:
        for r in all_results[:5]:
            print_trades(r)

    # 차트 저장
    if not args.no_chart:
        if args.strategy == "all":
            best: dict[str, object] = {}
            for r in all_results:
                if r.ticker not in best or r.total_return_pct > best[r.ticker].total_return_pct:
                    best[r.ticker] = r
            chart_results = list(best.values())
        else:
            chart_results = all_results

        print("\n차트 저장 중...")
        save_chart(chart_results)


if __name__ == "__main__":
    main()
