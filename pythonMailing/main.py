import schedule
import time
import logging
from datetime import datetime
import config
from news_fetcher import fetch_latest_ai_news
from email_sender import send_email

logger = logging.getLogger(__name__)

def job():
    """Main job function that fetches news and sends email."""
    logger.info("="*50)
    logger.info("Starting AI News Mailing Job")
    logger.info("="*50)
    
    try:
        # 1. Fetch the latest news (2 per topic = 8 total)
        news_items = fetch_latest_ai_news()
        
        if news_items:
            logger.info(f"Successfully fetched {len(news_items)} news articles.")
            
            # 2. Build email subject with today's date
            now = datetime.now()
            date_str = now.strftime("%Y년 %m월 %d일")
            subject = f"[Share]Daliy AI & ML News Auto Mailing {date_str}"
            
            if send_email(subject, news_items):
                logger.info("Email sent successfully.")
            else:
                logger.warning("Email sending failed.")
        else:
            logger.warning("No articles found to send.")
    except Exception as e:
        logger.error(f"Job execution failed: {type(e).__name__}: {e}", exc_info=True)
    finally:
        logger.info("="*50)
        logger.info("Job Finished")
        logger.info("="*50 + "\n")

def main():
    """Main function that initializes and runs the scheduler."""
    logger.info("Welcome to the AI News Automated Mailing System.")
    logger.info("Scheduling daily run at 08:00 AM KST.")
    
    # Run immediately on startup
    logger.info("Executing immediate run...")
    job()
    
    # Schedule to run once every day at 08:00 AM
    schedule.every().day.at("08:00").do(job)
    
    logger.info("Scheduler is running. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Exiting the AI News Automated Mailing System.")
        return

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Critical error in main: {type(e).__name__}: {e}", exc_info=True)
        exit(1)
