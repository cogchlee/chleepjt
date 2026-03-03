import os
import time
import logging
import random
from datetime import datetime
import pyupbit
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Logger settings (English to prevent encoding issues on Windows Cmd)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] %(message)s')

# ==========================================
# 1. Configuration
# ==========================================
ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY", "YOUR_ACCESS_KEY")
SECRET_KEY = os.getenv("UPBIT_SECRET_KEY", "YOUR_SECRET_KEY")

# TEST_MODE: True (Mock Trading), False (Real Trading)
TEST_MODE = os.getenv("TEST_MODE", "True").lower() in ("true", "1", "t")

# How many coins to trade? You can list up to 100-200.
# However, trading ALL 120+ KRW pairs can dilute capital and hit API rate limits (10 req/sec max).
# Best strategy for 100 coins:
# 1. Fetch pyupbit.get_tickers(fiat="KRW")
# 2. Sort by 24h trading volume and pick the top 20~30 coins to ensure liquidity.
# Here, we dynamically fetch the top 20 KRW pairs by trade volume.
def get_top_volume_tickers(limit=20):
    try:
        tickers = pyupbit.get_tickers(fiat="KRW")
        # Optimization: getting current prices/info for all tickers at once
        # pyupbit.get_current_price can accept a list of tickers
        # But to reliably get top volume, we could just static allocate top majors for now 
        # to avoid complex logic, but let's grab the top symbols.
        logging.info(f"Fetching top {limit} tickers by transaction volume...")
        
        # Upbit allows fetching ticker data in bulk
        url = "https://api.upbit.com/v1/ticker"
        import requests
        headers = {"accept": "application/json"}
        # Split into chunks of 100 max per request officially, but we can usually request all KRW
        res = requests.get(f"{url}?markets={','.join(tickers)}", headers=headers)
        data = res.json()
        
        # Sort by acc_trade_price_24h (24h traded amount in KRW)
        sorted_data = sorted(data, key=lambda x: x['acc_trade_price_24h'], reverse=True)
        top_tickers = [item['market'] for item in sorted_data[:limit]]
        return top_tickers
    except Exception as e:
        logging.error(f"Failed to fetch top volume tickers: {e}")
        return ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"]

# Setup Tickers (e.g., monitor Top 10 coins by volume for testing)
TICKERS = get_top_volume_tickers(limit=10)

# Volatility Breakout K-value (Usually 0.5)
K_VALUE = 0.5

# ==========================================
# 2. Data & Signals
# ==========================================
def get_current_prices_bulk(tickers):
    """Fetch current prices for multiple tickers at once to save API calls"""
    try:
        prices = pyupbit.get_current_price(tickers)
        if isinstance(prices, float):  # If only 1 ticker was passed
            return {tickers[0]: prices}
        return prices
    except Exception as e:
        logging.error(f"Bulk price fetch failed: {e}")
        return None

def get_target_price(ticker, k=K_VALUE):
    """
    Volatility Breakout Target Price = Today Open + (Yesterday High - Yesterday Low) * K
    """
    try:
        df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
        if df is not None and len(df) >= 2:
            target_price = df.iloc[1]['open'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
            return target_price
        return None
    except Exception as e:
        logging.error(f"[{ticker}] Target price fetch failed: {e}")
        time.sleep(0.12) # Rate limit handling
        return None

def get_balance(upbit, ticker="KRW"):
    if TEST_MODE:
        return 10000000  # Mock KRW balance (10 million KRW) 

    try:
        balances = upbit.get_balances()
        for b in balances:
            if b['currency'] == ticker.replace("KRW-", "") if "-" in ticker else ticker:
                if b['balance'] is not None:
                    return float(b['balance'])
                return 0
        return 0
    except Exception as e:
        logging.error(f"Balance fetch failed: {e}")
        return 0

# ==========================================
# 3. Execution (Buy/Sell)
# ==========================================
def buy_order(upbit, ticker, price):
    if TEST_MODE:
        logging.info(f"[TEST_MODE] {ticker} 🚀 BOUGHT at {price:,.2f} KRW (Mock)")
        return {"uuid": "test-buy-uuid"}
        
    logging.info(f"[{ticker}] 🚀 Executing REAL Market BUY Order!")
    try:
        krw = get_balance(upbit, "KRW")
        # Divide capital by max concurrent holdings (e.g. len(TICKERS))
        buy_amount = (krw / len(TICKERS)) * 0.9995 
        
        if buy_amount > 5000:
            res = upbit.buy_market_order(ticker, buy_amount)
            logging.info(f"[{ticker}] BUY Result: {res}")
            return res
        else:
            logging.warning(f"[{ticker}] Insufficient KRW balance: {buy_amount}")
            return None
    except Exception as e:
        logging.error(f"[{ticker}] BUY Order failed: {e}")
        return None

def sell_order(upbit, ticker, price):
    if TEST_MODE:
        logging.info(f"[TEST_MODE] {ticker} 💰 SOLD at {price:,.2f} KRW (Mock)")
        return {"uuid": "test-sell-uuid"}

    logging.info(f"[{ticker}] 💰 Executing REAL Market SELL Order!")
    try:
        volume = get_balance(upbit, ticker)
        if volume > 0:
            res = upbit.sell_market_order(ticker, volume)
            logging.info(f"[{ticker}] SELL Result: {res}")
            return res
        else:
            logging.warning(f"[{ticker}] No holding volume to sell.")
            return None
    except Exception as e:
        logging.error(f"[{ticker}] SELL Order failed: {e}")
        return None

# ==========================================
# 4. Main Loop
# ==========================================
def main():
    mode_text = "[TEST_MODE - Mock Trading]" if TEST_MODE else "[REAL_MODE - Actual Trading]"
    logging.info(f"🌟 Starting Crypto Auto-Trading Program {mode_text}")
    logging.info(f"Monitoring Top {len(TICKERS)} Coins: {TICKERS}")
    
    upbit = None
    if not TEST_MODE:
        upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)
    
    is_holding = {ticker: False for ticker in TICKERS}
    target_prices = {}
    
    # Pre-calculate target prices for all tickers
    for ticker in TICKERS:
        tp = get_target_price(ticker)
        if tp:
            target_prices[ticker] = tp
            logging.info(f"[{ticker}] Target Price calculated: {tp:,.2f} KRW")
            
    last_update_date = datetime.now().date()
    
    # [For TEST_MODE] Variables to simulate fake price spikes
    loop_counter = 0 
    
    while True:
        try:
            now = datetime.now()
            loop_counter += 1
            
            # Reset daily at 09:00 AM KST
            if now.hour == 9 and now.minute == 0 and now.date() != last_update_date:
                logging.info("09:00 KST Reached. Liquidating all holdings and recalculating targets.")
                for ticker in TICKERS:
                    if is_holding[ticker]:
                        sell_order(upbit, ticker, get_current_prices_bulk([ticker]).get(ticker, 0))
                        is_holding[ticker] = False
                
                time.sleep(10)
                
                for ticker in TICKERS:
                    tp = get_target_price(ticker)
                    if tp: target_prices[ticker] = tp
                    logging.info(f"[{ticker}] Renewed Target Price: {tp:,.2f} KRW")
                    
                last_update_date = now.date()
            
            # 1. Fetch ALL current prices in one API call for efficiency
            current_prices = get_current_prices_bulk(TICKERS)
            if not current_prices:
                time.sleep(1)
                continue
                
            for ticker in TICKERS:
                current_price = current_prices.get(ticker)
                
                if not current_price or ticker not in target_prices:
                    continue
                    
                target_price = target_prices[ticker]
                
                # --- [TEST_MODE] SIMULATING PRICE MOVEMENTS ---
                if TEST_MODE:
                    # Artificially spike the current price up or down randomly in testing
                    # Every ~5 loops, force one coin to pass the target price to show Buy Signal
                    if not is_holding[ticker] and loop_counter % 5 == 0 and random.random() > 0.8:
                        fake_price = target_price * 1.01  # +1% over target
                        logging.debug(f"[{ticker}] Simulating price spike to {fake_price:,.2f}...")
                        current_price = fake_price
                        
                    # Force sell signal
                    elif is_holding[ticker] and loop_counter % 5 == 0 and random.random() > 0.8:
                        fake_price = target_price * 1.04  # >3% profit target
                        logging.debug(f"[{ticker}] Simulating profit spike to {fake_price:,.2f}...")
                        current_price = fake_price
                # ----------------------------------------------
                
                # [BUY CONDITION]: Not holding & Current price exceeds Target price
                if not is_holding[ticker] and current_price >= target_price:
                    logging.info(f"[{ticker}] � BUY SIGNAL! Current: {current_price:,.2f} >= Target: {target_price:,.2f}")
                    res = buy_order(upbit, ticker, current_price)
                    if res:
                        is_holding[ticker] = True
                    
                # [SELL CONDITION]: Intraday take-profit (e.g. 3% profit)
                elif is_holding[ticker] and current_price >= target_price * 1.03:
                    logging.info(f"[{ticker}] 💵 3% PROFIT SIGNAL! Current: {current_price:,.2f}")
                    res = sell_order(upbit, ticker, current_price)
                    if res:
                        is_holding[ticker] = False
                
            # Sleep slightly to avoid Upbit rate limits (10 req/s for Non-Order APIs)
            # Bulk fetching prevents hitting the limit as fast
            time.sleep(0.5)
            
        except Exception as e:
            logging.error(f"Main Loop Error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
