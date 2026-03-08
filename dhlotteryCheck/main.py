import schedule
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

from lotto_analyzer import fetch_lotto_history, predict_lotto, predict_pension720
from triple_luck_analyzer import analyze_triple_luck_times
from mailer import send_lottery_email

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def job_weekly_lottery():
    """
    Fetches the latest distributions (simulated dataset refresh),
    generates 10 cases for Lotto 6/45 and Pension 720+, and emails the results.
    Runs every Sunday.
    """
    logger.info("Executing Weekly Lottery Prediction Job...")
    
    # 1. Lotto 6/45
    freqs = fetch_lotto_history()
    lotto_cases = predict_lotto(freqs, num_cases=10)
    
    # 2. Pension 720
    pension_cases = predict_pension720(num_cases=10)
    
    # 3. Format Email
    subject = f"[Lottery AI] 주간 로또 & 연금복권 AI 예측 리포트 ({datetime.now().strftime('%m/%d')})"
    html = "<h2>🎰 로또 6/45 AI 추천 조합 (10게임)</h2>"
    html += "<ul>"
    for i, case in enumerate(lotto_cases, 1):
        html += f"<li><strong>Game {i}:</strong> {', '.join(map(str, case))}</li>"
    html += "</ul>"
    
    html += "<h2>🎫 연금복권 720+ AI 추천 조합 (10게임)</h2>"
    html += "<ul>"
    for i, case in enumerate(pension_cases, 1):
        html += f"<li><strong>Game {i}:</strong> {case}</li>"
    html += "</ul>"
    
    html += "<p><em>면책 조항: 본 시스템의 예측은 과거 통계에 입각한 무작위 난수의 결과이며 당첨을 보장하지 않습니다.</em></p>"
    
    send_lottery_email(subject, html)

def job_triple_luck():
    """
    Analyzes triple luck historical times and emails a recommendation
    Runs 3x daily (06:00, 13:00, 19:00).
    """
    logger.info("Executing periodic Triple Luck analysis job...")
    recommendation = analyze_triple_luck_times()
    
    subject = f"[Triple Luck] 실시간 구매 최적의 시간 추천 ({datetime.now().strftime('%H:%M')})"
    html = "<h2>🍀 트리플럭 당첨 확률 예측 리포트</h2>"
    html += f"<p style='font-size: 16px; color: #2c3e50; font-weight: bold;'>{recommendation}</p>"
    html += "<p><em>* 전자복권은 동행복권의 발매 수량 및 당첨 현황에 따라 변동될 수 있습니다.</em></p>"
    
    send_lottery_email(subject, html)

def main():
    logger.info("Starting Auto Lottery Prediction Bot [dhlotteryCheck]...")
    
    # Immediate test run upon boot (optional, uncomment to test straight away)
    # job_weekly_lottery()
    # job_triple_luck()
    
    # 1. Weekly Schedule: Every Sunday at 00:00 (for Lotto & Pension)
    schedule.every().sunday.at("00:00").do(job_weekly_lottery)
    
    # 2. Daily Schedule: Triple Luck reporting (06:00, 13:00, 19:00)
    schedule.every().day.at("06:00").do(job_triple_luck)
    schedule.every().day.at("13:00").do(job_triple_luck)
    schedule.every().day.at("19:00").do(job_triple_luck)
    
    logger.info("Scheduler correctly initialized. Waiting for trigger...")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down the Lottery Agent...")

if __name__ == "__main__":
    main()
