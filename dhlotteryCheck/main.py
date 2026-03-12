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

def job_daily_report():
    """
    Combines Lotto 6/45, Pension 720+, and Triple Luck analysis into a single
    email report sent 3 times a day.
    """
    logger.info("Executing Consolidated Daily Lottery Report...")
    
    # 1. Lotto 6/45
    freqs = fetch_lotto_history()
    lotto_cases = predict_lotto(freqs, num_cases=5) # Reduced to 5 to keep mail clean
    
    # 2. Pension 720
    pension_cases = predict_pension720(num_cases=5) # Reduced to 5
    
    # 3. Triple Luck
    tl_recommendation = analyze_triple_luck_times()
    
    # Formulate Clean HTML Email
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    subject = f"[Lottery AI] 통합 복권 분석 리포트 ({now_str})"
    
    html = f"""
    <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: auto;">
        <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px;">
            📊 종합 복권 분석 리포트
        </h2>
        
        <h3 style="color: #e67e22;">🍀 트리플럭 (즉석 전자복권) 구매 추천</h3>
        <p style="background: #fdf2e9; padding: 10px; border-radius: 5px;">
            {tl_recommendation}
        </p>

        <h3 style="color: #27ae60;">🎰 로또 6/45 (최적화 5게임)</h3>
        <p style="font-size: 13px; color: #7f8c8d;">
            *과거 출현 빈도를 분석하여, 통계적으로 흔치 않은 패턴(모든 번호대 출현 등)을 배제하고 현실적인 극단성(특정 번호대 전멸, 3연속 번호 등)을 논리적으로 반영했습니다.
        </p>
        <ul style="background: #eaeded; padding: 15px 30px; border-radius: 5px;">
    """
    for i, case in enumerate(lotto_cases, 1):
        html += f"<li style='margin-bottom: 5px;'><strong>Game {i}:</strong> {', '.join(map(str, case))}</li>"
        
    html += """
        </ul>

        <h3 style="color: #8e44ad;">🎫 연금복권 720+ (최적화 5게임)</h3>
        <p style="font-size: 13px; color: #7f8c8d;">
            *0~9까지의 독립 시행 룰을 적용하여 수학적으로 흔하게 발생하는 '중복 숫자(2~4개)' 패턴을 есте스럽게 포함하되, 111111 같은 특이 케이스만 차단했습니다.
        </p>
        <ul style="background: #f4ecf7; padding: 15px 30px; border-radius: 5px;">
    """
    for i, case in enumerate(pension_cases, 1):
        html += f"<li style='margin-bottom: 5px;'><strong>Game {i}:</strong> {case}</li>"
        
    html += """
        </ul>
        
        <p style="font-size: 12px; color: #bdc3c7; text-align: center; margin-top: 30px;">
            본 시스템의 예측은 과거 통계 및 알고리즘 시뮬레이션에 입각한 결과이며 당첨을 보장하지 않습니다.
        </p>
    </div>
    """
    
    send_lottery_email(subject, html)

def main():
    logger.info("Starting Auto Lottery Prediction Bot [dhlotteryCheck]...")
    
    # Immediate test run upon boot (optional, uncomment to test straight away)
    # job_weekly_lottery()
    # job_triple_luck()
    
    # Daily Schedule: Consolidated report (06:00, 13:00, 19:00)
    schedule.every().day.at("06:00").do(job_daily_report)
    schedule.every().day.at("13:00").do(job_daily_report)
    schedule.every().day.at("19:00").do(job_daily_report)
    
    logger.info("Scheduler correctly initialized. Waiting for trigger...")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down the Lottery Agent...")

if __name__ == "__main__":
    main()
