from main import TICKERS, get_top_volume_tickers
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] %(message)s')

def test_wrapper():
    logging.info("Starting a simulated 5-minute Mock Auto-Trading Program.")
    logging.info(f"Target Coins Limit: {len(TICKERS)}")

    # Setup the variables that exist in main.py but tailored here if we want to run them dynamically
    import main
    import time
    from main import get_current_prices_bulk, get_target_price
    
    # 5 minutes simulation bounds
    RUNTIME_SECONDS = 5 * 60
    
    start_time = time.time()
    
    # Fake balance system
    MOCK_KRW = 100000.0  # 100,000 KRW
    MOCK_HOLDINGS = {t: 0.0 for t in main.TICKERS}
    
    loop_counter = 0

    while time.time() - start_time < RUNTIME_SECONDS:
        loop_counter += 1
        
        current_prices = get_current_prices_bulk(main.TICKERS)
        if not current_prices:
            time.sleep(1)
            continue
            
        for ticker in main.TICKERS:
            current_price = current_prices.get(ticker)
            if not current_price: continue
                
            # Simulate target prices dynamically for the test (just +1% of current price as target for mock testing)
            target_price = current_price * 1.01 
            
            is_holding = (MOCK_HOLDINGS[ticker] > 0)
            
            import random
            
            # --- [TEST_MODE] SIMULATING PRICE MOVEMENTS ---
            # Artificially spike the current price up or down randomly in testing
            # Every ~5 loops, force one coin to pass the target price to show Buy Signal
            if not is_holding and loop_counter % 5 == 0 and random.random() > 0.8:
                fake_price = target_price * 1.01  # +1% over target
                logging.debug(f"[{ticker}] Simulating price spike to {fake_price:,.2f}...")
                current_price = fake_price
                
            # Force sell signal
            elif is_holding and loop_counter % 5 == 0 and random.random() > 0.8:
                # Average profit spike
                fake_price = current_price * 1.04 
                logging.debug(f"[{ticker}] Simulating profit spike to {fake_price:,.2f}...")
                current_price = fake_price
            
            # [BUY CONDITION]: Not holding & Current price exceeds Target price
            if not is_holding and current_price >= target_price:
                logging.info(f"[{ticker}] 📈 BUY SIGNAL! Current: {current_price:,.2f} >= Target: {target_price:,.2f}")
                
                # Buy Logic (Max 20% of balance per coin to diversify)
                buy_amount = min(MOCK_KRW * 0.2, MOCK_KRW) 
                if buy_amount > 5000:
                    fee = buy_amount * 0.0005
                    units = (buy_amount - fee) / current_price
                    MOCK_KRW -= buy_amount
                    MOCK_HOLDINGS[ticker] = units
                    logging.info(f"[TEST_MODE] {ticker} 🚀 BOUGHT {units:.4f} at {current_price:,.2f} KRW | Rem KRW: {MOCK_KRW:,.0f}")
                
            # [SELL CONDITION]: Intraday take-profit (e.g. 3% profit)
            # For testing, since target_price is dynamic, let's just trigger random sells if price went up
            elif is_holding and current_price >= (buy_amount / MOCK_HOLDINGS[ticker]) * 1.03:
                logging.info(f"[{ticker}] 💵 PROFIT SIGNAL! Current: {current_price:,.2f}")
                
                # Sell Logic
                units = MOCK_HOLDINGS[ticker]
                revenue = units * current_price
                fee = revenue * 0.0005
                MOCK_KRW += (revenue - fee)
                MOCK_HOLDINGS[ticker] = 0.0
                logging.info(f"[TEST_MODE] {ticker} 💰 SOLD at {current_price:,.2f} KRW | Rev: {revenue:,.0f} | Cur KRW: {MOCK_KRW:,.0f}")

        # Sleep to avoid rate limits
        time.sleep(1)

    logging.info("=========================================")
    logging.info("5-minute Simulation Completed!")
    
    # Liquidate everything at current prices
    current_prices = get_current_prices_bulk(main.TICKERS)
    for ticker, units in MOCK_HOLDINGS.items():
        if units > 0:
            price = current_prices.get(ticker, 0)
            revenue = units * price
            fee = revenue * 0.0005
            MOCK_KRW += (revenue - fee)
            
    logging.info(f"FINAL MOCK KRW BALANCE: {MOCK_KRW:,.0f} KRW")
    logging.info(f"NET PROFIT/LOSS: {MOCK_KRW - 100000:,.0f} KRW ({(MOCK_KRW - 100000)/100000 * 100:.2f}%)")
    logging.info("=========================================")

if __name__ == '__main__':
    test_wrapper()
