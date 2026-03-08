import schedule
import time
import logging
from datetime import datetime
import config
from news_fetcher import fetch_news_for_category
from email_sender import send_email

logger = logging.getLogger(__name__)

def job_for_category(category):
    """Job function that fetches news and sends email for a specific category."""
    logger.info("="*50)
    logger.info(f"Starting Job for Category: {category['name']}")
    logger.info("="*50)
    
    try:
        # Fetch articles for this category
        news_items = fetch_news_for_category(category)
        
        if news_items:
            logger.info(f"Successfully fetched {len(news_items)} news articles for {category['name']}.")
            
            # Build email subject with today's KST date
            now = datetime.now()
            date_str = now.strftime("%Y년 %m월 %d일")
            subject = f"{category['email_subject_prefix']} {date_str}"
            
            if send_email(subject, news_items, category['credentials'], header_title=category['email_subject_prefix']):
                logger.info(f"Email sent successfully for {category['name']}.")
            else:
                logger.warning(f"Email sending failed for {category['name']}.")
        else:
            logger.warning(f"No articles found to send for {category['name']}.")
                
    except Exception as e:
        logger.error(f"Job execution failed for {category['name']}: {type(e).__name__}: {e}", exc_info=True)
    finally:
        logger.info("-" * 40)

def setup_schedule():
    """
    Sets up the scheduler based on category schedules:
      - 'Xm'          : Run every X minutes  (e.g. '10m', '30m')
      - 'twice_daily' : Run at 08:00 and 16:00 KST
      - 'once_daily'  : Run at 08:00 KST only
    Falls back to 'once_daily' if value is unrecognized.
    """
    active_cats = config.get_active_categories()
    if not active_cats:
        logger.warning("No active categories found with valid credentials. Nothing to schedule.")
        return

    for category in active_cats:
        schedule_type = category.get("schedule_type", "once_daily")
        cat_name = category['name']
        logger.info(f"Configuring schedule '{schedule_type}' for '{cat_name}'.")

        if schedule_type.endswith('m'):
            try:
                minutes = int(schedule_type[:-1])
                logger.info(f"Scheduling runs every {minutes} minutes for {cat_name}.")
                schedule.every(minutes).minutes.do(job_for_category, category)
                continue
            except ValueError:
                logger.warning(f"Invalid interval format '{schedule_type}' for {cat_name}. Falling back to once_daily.")
                schedule_type = 'once_daily'

        if schedule_type == 'twice_daily':
            logger.info(f"Scheduling runs at 08:00 AM and 04:00 PM KST for {cat_name}.")
            schedule.every().day.at("08:00").do(job_for_category, category)
            schedule.every().day.at("16:00").do(job_for_category, category)
        else:
            if schedule_type != 'once_daily':
                logger.warning(f"Unknown SCHEDULE_TYPE '{schedule_type}' for {cat_name}. Defaulting to once_daily (08:00 KST).")
            else:
                logger.info(f"Scheduling one daily run at 08:00 AM KST for {cat_name}.")
            schedule.every().day.at("08:00").do(job_for_category, category)

def main():
    """Main function that initializes and runs the scheduler."""
    logger.info("Welcome to the AI News Automated Mailing System.")

    # Set up recurring schedule
    setup_schedule()

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
