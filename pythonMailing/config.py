import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ai_news_mailing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# SMTP Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

# Receiver Configuration
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")
FORWARD_EMAIL = os.getenv("FORWARD_EMAIL", "")

# News Configuration
# Each topic has a Korean RSS feed (url_ko) tried first, then English (url_en) as fallback.
RSS_FEEDS = [
    {
        "topic": "AI Agent, AI Tool, AI Assistant",
        "url_ko": "https://news.google.com/rss/search?q=AI+%28%EC%97%90%EC%9D%B4%EC%A0%84%ED%8A%B8+OR+%ED%88%B4+OR+%EC%96%B4%EC%8B%9C%EC%8A%A4%ED%84%B4%ED%8A%B8%29+AND+%28%EA%B8%B0%EC%88%A0+OR+%EB%8F%99%ED%96%A5+OR+%EC%82%AC%EC%97%85%29&hl=ko&gl=KR&ceid=KR:ko",
        "url_en": "https://news.google.com/rss/search?q=AI+%28Agent+OR+Tool+OR+Assistant%29+AND+%28technology+OR+trend+OR+business+OR+research%29&hl=en-US&gl=US&ceid=US:en"
    },
    {
        "topic": "Machine Learning Articles",
        "url_ko": "https://news.google.com/rss/search?q=%EB%A8%B8%EC%8B%A0%EB%9F%AC%EB%8B%9D+AND+%28%EA%B8%B0%EC%88%A0+OR+%EB%8F%99%ED%96%A5+OR+%EC%82%AC%EC%97%85+OR+%EC%97%B0%EA%B5%AC%29&hl=ko&gl=KR&ceid=KR:ko",
        "url_en": "https://news.google.com/rss/search?q=%22Machine+Learning%22+AND+%28technology+OR+trend+OR+business+OR+academic%29&hl=en-US&gl=US&ceid=US:en"
    },
    {
        "topic": "Image Processing, Computer Vision Articles",
        "url_ko": "https://news.google.com/rss/search?q=%28%EC%9D%B4%EB%AF%B8%EC%A7%80+%EC%B2%98%EB%A6%AC+OR+%EC%BB%B4%ED%93%A8%ED%84%B0+%EB%B9%84%EC%A0%84%29+AND+%28%EA%B8%B0%EC%88%A0+OR+%EB%8F%99%ED%96%A5+OR+%EC%82%AC%EC%97%85%29&hl=ko&gl=KR&ceid=KR:ko",
        "url_en": "https://news.google.com/rss/search?q=%28%22Image+Processing%22+OR+%22Computer+Vision%22%29+AND+%28technology+OR+trend+OR+business+OR+academic%29&hl=en-US&gl=US&ceid=US:en"
    },
    {
        "topic": "AI, ML, CV, Image Processing Related Papers",
        "url_ko": "https://news.google.com/rss/search?q=%28AI+OR+%EB%A8%B8%EC%8B%A0%EB%9F%AC%EB%8B%9D+OR+%EC%BB%B4%ED%93%A8%ED%84%B0%EB%B9%84%EC%A0%84+OR+%EC%9D%B4%EB%AF%B8%EC%A7%80%EC%B2%98%EB%A6%AC%29+AND+%28%EB%85%BC%EB%AC%B8+OR+%EC%97%B0%EA%B5%AC%29&hl=ko&gl=KR&ceid=KR:ko",
        "url_en": "https://news.google.com/rss/search?q=%28AI+OR+%22Machine+Learning%22+OR+%22Computer+Vision%22+OR+%22Image+Processing%22%29+AND+%28paper+OR+research+OR+study+OR+academic%29&hl=en-US&gl=US&ceid=US:en"
    }
]

# Schedule Configuration
# SCHEDULE_TYPE options:
#   'Xm'          -> run every X minutes (e.g. '10m', '30m')
#   'twice_daily' -> run at 08:00 AM and 04:00 PM KST
#   'once_daily'  -> run at 08:00 AM KST only
SCHEDULE_TYPE = os.getenv("SCHEDULE_TYPE", "once_daily")

# Configuration Validation
def validate_config():
    """
    Validates that all required configuration values are set.
    Raises ValueError if critical configuration is missing.
    """
    required_fields = {
        "SENDER_EMAIL": SENDER_EMAIL,
        "SENDER_PASSWORD": SENDER_PASSWORD,
        "RECEIVER_EMAIL": RECEIVER_EMAIL,
    }
    
    missing_fields = [key for key, value in required_fields.items() if not value]
    
    if missing_fields:
        error_msg = f"Missing required configuration: {', '.join(missing_fields)}. Please set these in your .env file."
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info("Configuration validation passed.")

# Validate config on import
try:
    validate_config()
except ValueError as e:
    logger.warning(f"Configuration validation warning: {e}")

