"""
trade_utils.py
==============
Utility functions for the Upbit Auto Trading Bot.

Responsibilities:
  - Fetch top-volume tickers from market
  - Retrieve current prices in bulk
  - Calculate optimized K value and MA window per ticker using historical backtest
"""

import time
import logging
import requests
import pandas as pd
from typing import Optional

try:
    import pyupbit
except ImportError:
    logging.warning("pyupbit not installed. Please `pip install pyupbit`")
    pyupbit = None


# ---------------------------------------------------------------------------
# Market Data
# ---------------------------------------------------------------------------

def get_top_volume_tickers(limit: int = 100) -> list:
    """
    Fetch tickers from KRW market, sorted by 24h trading volume descending.
    Returns up to `limit` ticker symbols.
    """
    if not pyupbit:
        return []
    try:
        krw_tickers = pyupbit.get_tickers(fiat="KRW")
        all_ticker_data = []
        chunk_size = 50

        for i in range(0, len(krw_tickers), chunk_size):
            chunk = krw_tickers[i : i + chunk_size]
            url = f"https://api.upbit.com/v1/ticker?markets={','.join(chunk)}"
            resp = requests.get(url, headers={"accept": "application/json"}, timeout=5)
            if resp.status_code == 200:
                all_ticker_data.extend(resp.json())
            time.sleep(0.1)  # Respect Upbit API rate limits

        sorted_tickers = sorted(
            all_ticker_data,
            key=lambda x: x.get("acc_trade_price_24h", 0),
            reverse=True,
        )
        return [t["market"] for t in sorted_tickers[:limit]]

    except Exception as e:
        logging.error(f"[get_top_volume_tickers] {e}")
        return []


def get_current_prices_bulk(tickers: list) -> dict:
    """
    Fetch current prices for a list of tickers.
    Returns { 'KRW-BTC': 100000000, ... }
    Handles both single-value (float) and multi-value (dict) responses from pyupbit.
    """
    if not pyupbit:
        return {t: 0 for t in tickers}
    try:
        result = pyupbit.get_current_price(tickers)
        if isinstance(result, float):
            return {tickers[0]: result}
        return result or {}
    except Exception as e:
        logging.error(f"[get_current_prices_bulk] {e}")
        return {}


def get_ohlcv_safe(ticker: str, count: int) -> Optional[pd.DataFrame]:
    """
    Safely fetch daily OHLCV data for a ticker.
    Returns None if unavailable.
    """
    try:
        df = pyupbit.get_ohlcv(ticker, interval="day", count=count)
        if df is not None and len(df) >= count:
            return df
    except Exception as e:
        logging.debug(f"[get_ohlcv_safe] {ticker}: {e}")
    return None


# ---------------------------------------------------------------------------
# Parameter Optimisation (Periodic Learning Model)
# ---------------------------------------------------------------------------

def optimize_parameters(ticker: str, lookback_days: int = 14) -> tuple:
    """
    Find the best (K, MA) pair for a ticker using historical backtest.

    Strategy evaluated:
      - Volatility Breakout: target = open + (prev_high - prev_low) * K
      - MA trend filter:     only trade when today's open > MA of `ma` days
      - Daily ROR:           (close / target_price) * (1 - fee) when triggered, else 1
      - Objective:           maximise cumulative product of daily ROR

    Returns:
      (best_k: float, best_ma: int)
      Falls back to (0.5, 5) on error or insufficient data.
    """
    df = get_ohlcv_safe(ticker, lookback_days)
    if df is None:
        return 0.5, 5

    best_k, best_ma = 0.5, 5
    best_return = 1.0

    k_candidates  = [round(x * 0.1, 1) for x in range(1, 10)]   # 0.1 – 0.9
    ma_candidates = list(range(3, 11))                             # 3 – 10 days

    for k in k_candidates:
        for ma in ma_candidates:
            if ma > len(df):
                continue

            work = df.copy()
            work["ma"]     = work["close"].rolling(window=ma).mean()
            work["range"]  = (work["high"].shift(1) - work["low"].shift(1)) * k
            work["target"] = work["open"] + work["range"]
            work["is_bull"] = work["open"] > work["ma"].shift(1)

            # Daily return: fee = 0.05% on buy + 0.05% on sell = 0.1% round-trip
            def daily_ror(row):
                if (
                    pd.notna(row["target"])
                    and row["is_bull"]
                    and row["high"] >= row["target"]
                    and row["target"] > 0
                ):
                    return (row["close"] / row["target"]) * (1 - 0.001)
                return 1.0

            work["ror"] = work.apply(daily_ror, axis=1)
            total = work["ror"].cumprod().iloc[-1]

            if total > best_return:
                best_return = total
                best_k  = k
                best_ma = ma

    return best_k, best_ma


def build_ticker_params(tickers: list, lookback_days: int = 14) -> dict:
    """
    Run optimize_parameters for every ticker in the list.
    Returns { 'KRW-BTC': {'k': 0.3, 'ma': 5}, ... }
    Adds a short sleep between calls to avoid Upbit rate limits.
    """
    params = {}
    for ticker in tickers:
        best_k, best_ma = optimize_parameters(ticker, lookback_days)
        params[ticker] = {"k": best_k, "ma": best_ma}
        time.sleep(0.05)
    return params
