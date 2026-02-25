import schedule
import time
import pythonMailing.config
from pythonMailing.news_fetcher import fetch_latest_ai_news
from pythonMailing.email_sender import send_email

def job():
    print("\n--- Starting AI News Mailing Job ---")
    
    # 1. Fetch the latest news (limit defaults to 10 per theme)
    news_items = fetch_latest_ai_news()
    
    if news_items:
        print(f"Successfully fetched {len(news_items)} news articles.")
        # 2. Send the email
        subject = f"Your AI & ML News Update - {len(news_items)} Articles"
        send_email(subject, news_items)
    else:
        print("No news articles found to send.")
        
    print("--- Job Finished ---\n")

def main():
    print("Welcome to the AI News Automated Mailing System.")
    
    choice = config.SCHEDULE_TYPE
    
    print("\nExecuting immediate run...")
    job()
    
    if choice == '10m':
        print("\nScheduling runs every 10 minutes.")
        schedule.every(10).minutes.do(job)
    else:
        print("\nScheduling runs at 08:00 AM and 04:00 PM KST.")
        schedule.every().day.at("08:00").do(job)
        schedule.every().day.at("16:00").do(job)
    
    print("Scheduler is running. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60) # Wait one minute
    except KeyboardInterrupt:
        print("\nExiting the AI News Automated Mailing System.")

if __name__ == "__main__":
    main()
