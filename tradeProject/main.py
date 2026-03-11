"""
main.py
=======
Upbit Auto Trading Bot – Main Entry Point

Features:
  - Runs 24/7. Only stops on Ctrl+C (SIGINT) or SIGTERM.
  - On forced shutdown, prints a full trade summary & final asset value.
  - Initial parameter optimisation on startup.
  - Automatic re-optimisation every 24 h using the latest 14-day OHLCV data.
  - Top-100 KRW tickers by 24h trading volume, refreshed on each re-train cycle.
  - Simulation mode (default) uses 10,000 KRW as starting capital.
"""

import os
import time
import signal
import logging
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logging.warning("python-dotenv not installed. Skipping `.env` file load.")

try:
    import pyupbit
except ImportError:
    pyupbit = None

from trade_utils import (
    get_target_tickers,
    get_current_prices_bulk,
    get_ohlcv_safe,
    build_ticker_params,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] %(message)s",
)

ACCESS_KEY        = os.environ.get("UPBIT_ACCESS_KEY", "")
SECRET_KEY        = os.environ.get("UPBIT_SECRET_KEY", "")
SIMULATION_MODE   = os.environ.get("SIMULATION_MODE", "True").lower() in ("true", "1", "yes")

EMAIL_USER        = os.environ.get("EMAIL_USER", "")
EMAIL_PASSWORD    = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER    = os.environ.get("EMAIL_RECEIVER", "")

SIM_START_KRW     = 100_000.0   # Simulation starting balance (KRW)
TICKER_LIMIT      = 10          # Top 10 by volume + Top 10 by gain (max 20)
TRAIN_DAYS        = 14          # OHLCV look-back window for optimisation
RETRAIN_HOURS     = 24          # Re-optimise every N hours
BUY_RATIO         = 0.20        # Allocate 20 % of remaining KRW per buy
MIN_BUY_KRW       = 2000        # Minimum order size (KRW)
TAKE_PROFIT_RATIO = 0.05        # +5 % → sell (basic TP)
STOP_LOSS_RATIO   = -0.025      # −2.5 % → sell (basic SL)
TRAILING_ACTIVATE = 0.015       # Activate trailing stop when profit >= +1.5%
TRAILING_DROP     = 0.015       # Sell if price drops 1.5% from the peak
FEE_RATE          = 0.0005      # Upbit trading fee: 0.05 % per leg

# ---------------------------------------------------------------------------
# Global State (mutated by signal handler)
# ---------------------------------------------------------------------------
_shutdown_requested = False

# Simulation ledger
sim_krw       : float = SIM_START_KRW
sim_holdings  : dict  = {}  # { ticker: units }
sim_buy_prices: dict  = {}  # { ticker: buy_price }
highest_prices: dict  = {}  # { ticker: highest_buy_price } for trailing stop

# Trade history for final report
trade_log: list = []  # list of dicts


# ---------------------------------------------------------------------------
# Signal Handler
# ---------------------------------------------------------------------------
def _request_shutdown(signum, frame):
    global _shutdown_requested
    logging.info("Shutdown signal received. Finishing current cycle...")
    _shutdown_requested = True


signal.signal(signal.SIGINT,  _request_shutdown)
signal.signal(signal.SIGTERM, _request_shutdown)


# ---------------------------------------------------------------------------
# Trade Helpers
# ---------------------------------------------------------------------------

def _execute_buy(ticker: str, current_price: float, upbit=None):
    """Execute a buy order (simulation or real)."""
    global sim_krw

    if SIMULATION_MODE:
        buy_amount = min(sim_krw * BUY_RATIO, sim_krw)
        if buy_amount < MIN_BUY_KRW:
            return
        units = (buy_amount * (1 - FEE_RATE)) / current_price
        sim_krw             -= buy_amount
        sim_holdings[ticker] = sim_holdings.get(ticker, 0) + units
        sim_buy_prices[ticker] = current_price
        msg = (
            f"[BUY]  {ticker} @ {current_price:,.2f} KRW "
            f"| Invested: {buy_amount:,.2f} | Rem KRW: {sim_krw:,.2f}"
        )
        logging.info(msg)
        trade_log.append({"time": datetime.datetime.now(), "action": "BUY",
                          "ticker": ticker, "price": current_price,
                          "amount_krw": buy_amount, "units": units})
    else:
        krw = upbit.get_balance("KRW")
        buy_amount = min(krw * BUY_RATIO, krw)
        if buy_amount < MIN_BUY_KRW:
            return
        res = upbit.buy_market_order(ticker, buy_amount * (1 - FEE_RATE))
        logging.info(f"[REAL BUY] {ticker} → {res}")
        trade_log.append({"time": datetime.datetime.now(), "action": "BUY",
                          "ticker": ticker, "price": current_price,
                          "amount_krw": buy_amount})


def _execute_sell(ticker: str, current_price: float, profit_ratio: float, upbit=None):
    """Execute a sell order (simulation or real)."""
    global sim_krw

    signal_type = "TAKE PROFIT" if profit_ratio >= TAKE_PROFIT_RATIO else "STOP LOSS"

    if SIMULATION_MODE:
        units   = sim_holdings.get(ticker, 0)
        revenue = units * current_price * (1 - FEE_RATE)
        sim_krw += revenue
        sim_holdings[ticker]   = 0.0
        sim_buy_prices[ticker] = 0.0
        if ticker in highest_prices: del highest_prices[ticker]
        msg = (
            f"[SELL] {ticker} @ {current_price:,.2f} KRW "
            f"({signal_type}) | P&L: {profit_ratio*100:+.2f}% | Cur KRW: {sim_krw:,.2f}"
        )
        logging.info(msg)
        trade_log.append({"time": datetime.datetime.now(), "action": "SELL",
                          "ticker": ticker, "price": current_price,
                          "revenue_krw": revenue, "pnl_pct": profit_ratio * 100})
    else:
        volume = upbit.get_balance(ticker)
        res = upbit.sell_market_order(ticker, volume)
        if ticker in highest_prices: del highest_prices[ticker]
        logging.info(f"[REAL SELL] {ticker} ({signal_type}) → {res}")
        trade_log.append({"time": datetime.datetime.now(), "action": "SELL",
                          "ticker": ticker, "price": current_price,
                          "pnl_pct": profit_ratio * 100})


# ---------------------------------------------------------------------------
# Final Report
# ---------------------------------------------------------------------------
def print_final_report(tickers: list, upbit=None):
    """Print trade history and final asset summary before shutdown."""
    print("\n" + "=" * 60)
    print("  TRADE BOT SHUTDOWN REPORT")
    print("=" * 60)

    # Trade History
    if trade_log:
        print(f"\n{'#':>3}  {'Time':<21}  {'Action':<5}  {'Ticker':<12}  {'Price':>14}  {'P&L':>8}")
        print("-" * 75)
        for i, t in enumerate(trade_log, 1):
            pnl = f"{t.get('pnl_pct', 0):+.2f}%" if "pnl_pct" in t else "-"
            print(
                f"{i:>3}  {str(t['time'])[:19]:<21}  {t['action']:<5}  "
                f"{t['ticker']:<12}  {t['price']:>14,.2f}  {pnl:>8}"
            )
    else:
        print("\n  No trades executed during this session.")

    # Final asset calculation
    print("\n" + "-" * 60)
    if SIMULATION_MODE:
        total_asset = sim_krw
        print(f"  Remaining KRW (cash)  : {sim_krw:>15,.2f} KRW")
        for ticker, units in sim_holdings.items():
            if units > 0:
                price_data = get_current_prices_bulk([ticker])
                cur_price  = price_data.get(ticker, 0)
                value      = units * cur_price
                total_asset += value
                print(f"  Holdings {ticker:<10}: {units:.6f} units @ {cur_price:,.2f} = {value:,.2f} KRW")
        pnl_total = total_asset - SIM_START_KRW
        pnl_pct   = (pnl_total / SIM_START_KRW) * 100
        print(f"\n  Start Balance : {SIM_START_KRW:>15,.2f} KRW")
        print(f"  Final Assets  : {total_asset:>15,.2f} KRW")
        print(f"  Total P&L     : {pnl_total:>+15,.2f} KRW  ({pnl_pct:+.2f}%)")
    else:
        try:
            krw_balance = upbit.get_balance("KRW")
            print(f"  Remaining KRW: {krw_balance:,.2f} KRW")
        except Exception:
            print("  (Could not fetch real balance)")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Notification (Email)
# ---------------------------------------------------------------------------
def send_status_email(tickers: list, upbit=None):
    """Send an email containing the current trading status and balances formatted like the shutdown report."""
    if not EMAIL_USER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        return

    subject = f"[{'SIMULATION' if SIMULATION_MODE else 'REAL'}] Upbit Trading Bot Report"
    
    # CSS styling for the tables
    body = f"<h2>Trading Bot Status Report</h2>"
    body += f"<p><strong>Time:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
    body += """
    <style>
        table { border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
    """

    # 1. Final Asset Calculation Table (Summarized First)
    body += f"<h3>1. Asset Summary</h3>"
    body += "<table>"
    
    total_asset_value = 0.0
    if SIMULATION_MODE:
        total_asset_value = sim_krw
        body += f"<tr><td><strong>Remaining Cash (KRW)</strong></td><td colspan='2'>{sim_krw:,.2f}</td></tr>"
        body += "<tr><th>Holding</th><th>Units</th><th>Current Value (KRW)</th></tr>"
        
        for ticker, units in sim_holdings.items():
            if units > 0:
                price_data = get_current_prices_bulk([ticker])
                cur_price  = price_data.get(ticker, 0)
                value      = units * cur_price
                total_asset_value += value
                body += f"<tr><td>{ticker}</td><td>{units:.6f} @ {cur_price:,.2f}</td><td>{value:,.2f}</td></tr>"
                
        pnl_total = total_asset_value - SIM_START_KRW
        pnl_pct   = (pnl_total / SIM_START_KRW) * 100
        
        body += f"<tr><td><strong>Start Balance</strong></td><td colspan='2'>{SIM_START_KRW:,.2f}</td></tr>"
        body += f"<tr><td><strong>Total Assets</strong></td><td colspan='2'>{total_asset_value:,.2f}</td></tr>"
        color = "red" if pnl_total < 0 else "blue"
        body += f"<tr><td><strong>Total P&L</strong></td><td colspan='2' style='color:{color}'><b>{pnl_total:>+,.2f} ({pnl_pct:+.2f}%)</b></td></tr>"
    else:
        try:
            krw_balance = upbit.get_balance("KRW")
            body += f"<tr><td><strong>Remaining Cash (KRW)</strong></td><td colspan='2'>{krw_balance:,.2f}</td></tr>"
            body += "<tr><th>Holding</th><th>Units</th><th>Current Value (KRW)</th></tr>"
            
            # Fetch all accounts balances
            balances = upbit.get_balances()
            total_estimated_krw = krw_balance
            
            for b in balances:
                currency = b['currency']
                if currency == 'KRW': continue
                ticker = f"KRW-{currency}"
                if ticker in tickers:
                    units = float(b['balance'])
                    if units > 0:
                        cur_price = get_current_prices_bulk([ticker]).get(ticker, 0)
                        value = units * cur_price
                        total_estimated_krw += value
                        body += f"<tr><td>{ticker}</td><td>{units:.6f} @ {cur_price:,.2f}</td><td>{value:,.2f}</td></tr>"
            
            total_asset_value = total_estimated_krw
            body += f"<tr><td><strong>Total Estimated Assets (KRW)</strong></td><td colspan='2'>{total_estimated_krw:,.2f}</td></tr>"
        except Exception as e:
            body += f"<tr><td colspan='3'>Error fetching real balances: {e}</td></tr>"

    body += "</table>"

    # 2. Trade History Table (Last 24 Hours)
    cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=24)
    recent_logs = [t for t in trade_log if t['time'] >= cutoff_time]
    
    body += f"<h3>2. Trade History (Last 24 Hours)</h3>"
    if recent_logs:
        body += "<table>"
        body += "<tr><th>#</th><th>Time</th><th>Action</th><th>Ticker</th><th>Price (KRW)</th><th>P&L / Units</th></tr>"
        for i, t in enumerate(recent_logs, 1):
            time_str = str(t['time'])[:19]
            price_str = f"{t['price']:,.2f}"
            if t['action'] == "SELL":
                pnl = f"{t.get('pnl_pct', 0):+.2f}%"
            else:
                pnl = f"{t.get('units', 0):.6f} u" if SIMULATION_MODE else "-"
            body += f"<tr><td>{i}</td><td>{time_str}</td><td>{t['action']}</td><td>{t['ticker']}</td><td>{price_str}</td><td>{pnl}</td></tr>"
        body += "</table>"
    else:
        body += "<p>No trades executed in the last 24 hours.</p>"

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        logging.info("Status email report sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email report: {e}")

# ---------------------------------------------------------------------------
# Trading Loop (one full cycle per ticker chunk)
# ---------------------------------------------------------------------------
def trading_cycle(tickers: list, ticker_params: dict, upbit=None):
    """Process one cycle of price checks and buy/sell signals for all tickers."""
    chunk_size = 50
    for i in range(0, len(tickers), chunk_size):
        if _shutdown_requested:
            return
        chunk         = tickers[i : i + chunk_size]
        current_prices = get_current_prices_bulk(chunk)
        if not current_prices:
            continue

        for ticker in chunk:
            current_price = current_prices.get(ticker, 0)
            if current_price <= 0:
                continue

            params    = ticker_params.get(ticker, {"k": 0.5, "ma": 5})
            ma_window = params["ma"]
            k         = params["k"]

            is_holding = (
                sim_holdings.get(ticker, 0) > 0
                if SIMULATION_MODE
                else (upbit.get_balance(ticker) > 0)
            )

            if not is_holding:
                # ── BUY SIGNAL CHECK ─────────────────────────────────────
                # To calculate MA 20 we need at least 21 items
                lookback_req = max(ma_window, 20) + 1
                df = get_ohlcv_safe(ticker, lookback_req)
                if df is None or len(df) < 20:
                    continue

                ma_val     = df["close"].rolling(window=ma_window).mean().iloc[-2]
                ma20_val   = df["close"].rolling(window=20).mean().iloc[-2]
                prev_day   = df.iloc[-2]
                today_open = df.iloc[-1]["open"]
                target     = today_open + (prev_day["high"] - prev_day["low"]) * k

                # Uptrend condition: Price touches target, and open is above both short MA and long MA(20)
                if current_price >= target and today_open > ma_val and today_open > ma20_val:
                    _execute_buy(ticker, current_price, upbit)
                    highest_prices[ticker] = current_price

            else:
                # ── SELL SIGNAL CHECK ─────────────────────────────────────
                buy_price = (
                    sim_buy_prices.get(ticker, 0)
                    if SIMULATION_MODE
                    else upbit.get_avg_buy_price(ticker)
                )
                if buy_price <= 0:
                    continue

                # Trailing Stop Tracker Update
                peak_price = highest_prices.get(ticker, buy_price)
                if current_price > peak_price:
                    highest_prices[ticker] = current_price
                    peak_price = current_price

                profit_ratio = (current_price - buy_price) / buy_price
                drop_from_peak = (peak_price - current_price) / peak_price if peak_price > 0 else 0

                # Determine if sell is triggered
                # 1) Take Profit (hard limit) or
                # 2) Stop Loss (hard limit) or
                # 3) Trailing Stop (activated after a certain profit threshold, drops by TRAILING_DROP)
                triggered_trailing = profit_ratio >= TRAILING_ACTIVATE and drop_from_peak >= TRAILING_DROP

                if profit_ratio >= TAKE_PROFIT_RATIO or profit_ratio <= STOP_LOSS_RATIO or triggered_trailing:
                    _execute_sell(ticker, current_price, profit_ratio, upbit)


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
def main():
    global sim_krw, sim_holdings, sim_buy_prices

    logging.info("=" * 50)
    logging.info("  🚀  Upbit Auto Trading Bot  –  START")
    logging.info(f"  🔧  Mode   : {'SIMULATION' if SIMULATION_MODE else 'REAL TRADING'}")
    logging.info(f"  💰  Capital: {SIM_START_KRW:,.0f} KRW (sim)")
    logging.info("=" * 50)

    # Real-mode auth
    upbit = None
    if not SIMULATION_MODE:
        if not ACCESS_KEY or not SECRET_KEY:
            logging.error("API Keys missing for Real Mode. Exiting.")
            return
        upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)
        logging.info("Upbit real API connected.")

    sim_krw = SIM_START_KRW

    # ── Step 1 : Fetch top target tickers ───────────────────────────────
    logging.info(f"Fetching Top {TICKER_LIMIT} Volume and Top {TICKER_LIMIT} Gain tickers...")
    tickers = get_target_tickers(TICKER_LIMIT)
    logging.info(f"→ {len(tickers)} unique tickers selected.  Top-5: {tickers[:5]}")

    sim_holdings   = {t: 0.0 for t in tickers}
    sim_buy_prices = {t: 0.0 for t in tickers}

    # ── Step 2 : Initial parameter optimisation (learning phase) ─────────
    logging.info(f"Running initial parameter optimisation (lookback={TRAIN_DAYS}d)...")
    ticker_params  = build_ticker_params(tickers, TRAIN_DAYS)
    last_train_dt  = datetime.datetime.now()
    logging.info("Initial optimisation complete.  Starting trading loop...")

    # ── Step 3 : Main 24/7 trading loop ──────────────────────────────────
    last_email_sent_hour = -1

    try:
        while not _shutdown_requested:
            now = datetime.datetime.now()
            
            # Send email periodically (every 6 hours at 00, 06, 12, 18 KST)
            if now.hour in [0, 6, 12, 18] and now.hour != last_email_sent_hour:
                logging.info(f"Triggering scheduled status email (Hour: {now.hour})")
                send_status_email(tickers, upbit)
                last_email_sent_hour = now.hour

            # Periodic re-training
            hours_since_train = (now - last_train_dt).total_seconds() / 3600
            if hours_since_train >= RETRAIN_HOURS:
                logging.info(f"⏰ {RETRAIN_HOURS}h elapsed – refreshing tickers & re-optimising...")
                tickers        = get_target_tickers(TICKER_LIMIT)
                ticker_params  = build_ticker_params(tickers, TRAIN_DAYS)
                # Extend holdings dicts for any newly-added tickers
                for t in tickers:
                    sim_holdings.setdefault(t, 0.0)
                    sim_buy_prices.setdefault(t, 0.0)
                last_train_dt = datetime.datetime.now()
                logging.info("Re-optimisation complete.")

            trading_cycle(tickers, ticker_params, upbit)
            time.sleep(0.5)

    except Exception as e:
        logging.error(f"Unexpected error in main loop: {e}", exc_info=True)

    finally:
        # ── Shutdown report ───────────────────────────────────────────────
        print_final_report(tickers, upbit)


if __name__ == "__main__":
    main()
