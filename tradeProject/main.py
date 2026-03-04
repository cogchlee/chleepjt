import os
import time
import logging
from dotenv import load_dotenv

try:
    import pyupbit
except ImportError:
    logging.warning("pyupbit not installed. Please `pip install pyupbit`")
    pyupbit = None

# Load environment variables (e.g., from .env file)
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] %(message)s')

# ==========================================
# 1. Configuration & Global Variables
# ==========================================
ACCESS_KEY = os.environ.get("UPBIT_ACCESS_KEY", "")
SECRET_KEY = os.environ.get("UPBIT_SECRET_KEY", "")

# Determine mode: Simulation or Real
SIMULATION_MODE = os.environ.get("SIMULATION_MODE", "True").lower() in ["true", "1", "yes"]

# Default Tickers
# KRW-BTC (Bitcoin), KRW-ETH (Ethereum), KRW-XRP (Ripple), KRW-SOL (Solana), KRW-DOGE (Dogecoin)
TICKERS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"]

# ==========================================
# 2. Helper Functions for Data Fetching
# ==========================================
def get_top_volume_tickers(limit=5):
    """
    Fetch top tickers by 24h trading volume in KRW market.
    If pyupbit is not available or an error occurs, returns default TICKERS.
    """
    if not pyupbit: return TICKERS[:limit]
    try:
        krw_tickers = pyupbit.get_tickers(fiat="KRW")
        # To get actual top volume accurately, one would need to fetch all tickers' data.
        # This can be heavy, so we will just return the most popular ones for now
        # as a placeholder for top volume logic.
        return krw_tickers[:limit]
    except Exception as e:
        logging.error(f"Error fetching top tickers: {e}")
        return TICKERS[:limit]

def get_current_prices_bulk(tickers):
    """
    Fetch current prices for a list of tickers at once.
    Returns a dictionary: { 'KRW-BTC': 100000000, ... }
    """
    if not pyupbit: 
        # Dummy data for testing if no pyupbit
        return {t: 100000000 for t in tickers}
    try:
        return pyupbit.get_current_price(tickers)
    except Exception as e:
        logging.error(f"Error fetching bulk prices: {e}")
        return {}

def get_target_price(ticker, k=0.5):
    """
    Calculate the target buy price (Volatility Breakout Strategy).
    Range = Previous High - Previous Low
    Target = Today Open + Range * K
    """
    if not pyupbit: return 100000000
    try:
        df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
        if df is not None and len(df) >= 2:
            prev_day = df.iloc[0]
            today_open = df.iloc[1]['open']
            target = today_open + (prev_day['high'] - prev_day['low']) * k
            return target
    except Exception as e:
        logging.error(f"Error calculating target price for {ticker}: {e}")
    return 0

def get_ma(ticker, days=5):
    """
    Calculate the Moving Average for the given days.
    """
    if not pyupbit: return 90000000
    try:
        df = pyupbit.get_ohlcv(ticker, interval="day", count=days)
        if df is not None and len(df) >= days:
            return df['close'].mean()
    except Exception as e:
        logging.error(f"Error calculating MA{days} for {ticker}: {e}")
    return 0

# ==========================================
# 3. Main Logic & Loop
# ==========================================
def main():
    logging.info(f"=========================================")
    logging.info(f"🚀 Starting Upbit Auto Trading Bot")
    logging.info(f"🛠️ Mode: {'[SIMULATION]' if SIMULATION_MODE else '[REAL TRADING]'} ")
    logging.info(f"=========================================")

    # Initialize Upbit instance for Real Mode
    upbit = None
    if not SIMULATION_MODE:
        if not ACCESS_KEY or not SECRET_KEY:
            logging.error("API Keys missing for Real Mode. Exiting.")
            return
        upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)
        logging.info("Upbit real API connected.")

    # Tracking simulation balances
    sim_krw = 1000000.0  # Start with 1 million won
    sim_holdings = {t: 0.0 for t in TICKERS}
    sim_buy_prices = {t: 0.0 for t in TICKERS}

    while True:
        try:
            current_prices = get_current_prices_bulk(TICKERS)
            if not current_prices:
                time.sleep(1)
                continue

            for ticker in TICKERS:
                current_price = current_prices.get(ticker, 0)
                if current_price == 0: continue

                target_price = get_target_price(ticker, 0.5)
                ma5 = get_ma(ticker, 5)

                # Check if holding
                if SIMULATION_MODE:
                    is_holding = sim_holdings[ticker] > 0
                else:
                    is_holding = upbit.get_balance(ticker) > 0

                # --- 1. BUY LOGIC ---
                # Strategy: Volatility Breakout + MA5 Filter (Uptrend)
                if not is_holding and current_price >= target_price and current_price >= ma5:
                    logging.info(f"[{ticker}] 📈 BUY SIGNAL (Target: {target_price:,.0f} | MA5: {ma5:,.0f} | Cur: {current_price:,.0f})")
                    
                    if SIMULATION_MODE:
                        buy_amount = min(sim_krw * 0.2, sim_krw) # Use up to 20% of balance
                        if buy_amount >= 5000:
                            fee = buy_amount * 0.0005
                            units = (buy_amount - fee) / current_price
                            sim_krw -= buy_amount
                            sim_holdings[ticker] = units
                            sim_buy_prices[ticker] = current_price
                            logging.info(f"   [SIMULATION BUY] {ticker} - Rem KRW: {sim_krw:,.0f}")
                    else:
                        krw = upbit.get_balance("KRW")
                        buy_amount = min(krw * 0.2, krw)
                        if buy_amount >= 5000:
                            res = upbit.buy_market_order(ticker, buy_amount * 0.9995) # 0.05% buffer for fees
                            logging.info(f"   [REAL BUY] {ticker} - Result: {res}")

                # --- 2. SELL LOGIC ---
                # Sell simple profit-taking (e.g. +3%) or stop-loss (-2%)
                if is_holding:
                    buy_price = sim_buy_prices[ticker] if SIMULATION_MODE else upbit.get_avg_buy_price(ticker)
                    
                    if buy_price > 0:
                        profit_ratio = (current_price - buy_price) / buy_price
                        
                        # Sell if +3% or -2%
                        if profit_ratio >= 0.03 or profit_ratio <= -0.02:
                            signal_type = "PROFIT" if profit_ratio >= 0.03 else "STOP LOSS"
                            logging.info(f"[{ticker}] 📉 SELL SIGNAL ({signal_type}) - Ratio: {profit_ratio*100:.2f}%")
                            
                            if SIMULATION_MODE:
                                units = sim_holdings[ticker]
                                revenue = units * current_price
                                fee = revenue * 0.0005
                                sim_krw += (revenue - fee)
                                sim_holdings[ticker] = 0.0
                                sim_buy_prices[ticker] = 0.0
                                logging.info(f"   [SIMULATION SELL] {ticker} - Rev: {revenue:,.0f} | Cur KRW: {sim_krw:,.0f}")
                            else:
                                volume = upbit.get_balance(ticker)
                                res = upbit.sell_market_order(ticker, volume)
                                logging.info(f"   [REAL SELL] {ticker} - Result: {res}")

            # Sleep to avoid rate limits
            time.sleep(1)

        except Exception as e:
            logging.error(f"Error during execution: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
