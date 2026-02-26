import schedule
import time
import logging
from datetime import datetime
import config
from news_fetcher import fetch_latest_ai_news, save_sent_links
from email_sender import send_email

logger = logging.getLogger(__name__)

def job():
    """Main job function that fetches news and sends email."""
    logger.info("="*50)
    logger.info("Starting AI News Mailing Job")
    logger.info("="*50)
    
    try:
        # 1. Fetch the latest news (limit defaults to 3 per theme)
        news_items = fetch_latest_ai_news()
        
        if news_items:
            logger.info(f"Successfully fetched {len(news_items)} news articles.")
            
            # 2. Add custom email subject format using datetime for the title
            now = datetime.now()
            date_str = now.strftime("%Y년 %m월 %d일")
            subject = f"[Share]Daliy AI & ML News Auto Mailing {date_str}"
            
            if send_email(subject, news_items):
                # 3. Save sent links to avoid duplicates
                save_sent_links([item['link'] for item in news_items])
                logger.info("Job completed successfully.")
            else:
                logger.warning("Email sending failed.")
        else:
            logger.warning("No new articles found to send.")
    except Exception as e:
        logger.error(f"Job execution failed: {type(e).__name__}: {e}", exc_info=True)
    finally:
        logger.info("="*50)
        logger.info("Job Finished")
        logger.info("="*50 + "\n")

def main():
    """Main function that initializes and runs the scheduler."""
    logger.info("Welcome to the AI News Automated Mailing System.")
    
    choice = config.SCHEDULE_TYPE
    
    logger.info("Executing immediate run...")
    job()
    
    if choice.endswith('m'):
        try:
            minutes = int(choice[:-1])
            logger.info(f"Scheduling runs every {minutes} minutes.")
            schedule.every(minutes).minutes.do(job)
        except ValueError:
            logger.warning("Invalid schedule format. Defaulting to twice daily.")
            schedule.every().day.at("08:00").do(job)
            schedule.every().day.at("16:00").do(job)
    else:
        logger.info("Scheduling runs at 08:00 AM and 04:00 PM KST.")
        schedule.every().day.at("08:00").do(job)
        schedule.every().day.at("16:00").do(job)
    
    logger.info("Scheduler is running. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60) # Wait one minute
    except KeyboardInterrupt:
        logger.info("Exiting the AI News Automated Mailing System.")
        return

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Critical error in main: {type(e).__name__}: {e}", exc_info=True)
        exit(1)
