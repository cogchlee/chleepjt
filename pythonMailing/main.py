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
        # Fetch 2 articles per topic (4 topics = 8 total)
        news_items = fetch_latest_ai_news()
        
        if news_items:
            logger.info(f"Successfully fetched {len(news_items)} news articles.")
            
            # Build email subject with today's KST date
            now = datetime.now()
            date_str = now.strftime("%Y년 %m월 %d일")
            subject = f"[Share]Daily AI & ML News Auto Mailing {date_str}"
            
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

def setup_schedule(schedule_type: str):
    """
    Sets up the scheduler based on SCHEDULE_TYPE from .env:
      - 'Xm'          : Run every X minutes  (e.g. '10m', '30m')
      - 'twice_daily' : Run at 08:00 and 16:00 KST
      - 'once_daily'  : Run at 08:00 KST only
    Falls back to 'once_daily' if value is unrecognized.
    """
    if schedule_type.endswith('m'):
        try:
            minutes = int(schedule_type[:-1])
            logger.info(f"Scheduling runs every {minutes} minutes.")
            schedule.every(minutes).minutes.do(job)
            return
        except ValueError:
            logger.warning(f"Invalid interval format '{schedule_type}'. Falling back to once_daily.")

    if schedule_type == 'twice_daily':
        logger.info("Scheduling runs at 08:00 AM and 04:00 PM KST.")
        schedule.every().day.at("08:00").do(job)
        schedule.every().day.at("16:00").do(job)
    else:
        # Default: once_daily at 08:00
        if schedule_type != 'once_daily':
            logger.warning(f"Unknown SCHEDULE_TYPE '{schedule_type}'. Defaulting to once_daily (08:00 KST).")
        else:
            logger.info("Scheduling one daily run at 08:00 AM KST.")
        schedule.every().day.at("08:00").do(job)

def main():
    """Main function that initializes and runs the scheduler."""
    logger.info("Welcome to the AI News Automated Mailing System.")

    schedule_type = config.SCHEDULE_TYPE
    logger.info(f"SCHEDULE_TYPE = '{schedule_type}'")

    # Run immediately on startup
    logger.info("Executing immediate run...")
    job()

    # Set up recurring schedule
    setup_schedule(schedule_type)

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
