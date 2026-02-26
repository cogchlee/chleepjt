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
# We will use multiple Google News RSS feeds for specific topics.
RSS_FEEDS = [
    {
        "topic": "AI Agent, AI Tool, AI Assistant",
        "url": "https://news.google.com/rss/search?q=AI+%28Agent+OR+Tool+OR+Assistant%29+AND+%28technology+OR+trend+OR+business+OR+academic+OR+research%29&hl=en-US&gl=US&ceid=US:en"
    },
    {
        "topic": "Machine Learning Articles",
        "url": "https://news.google.com/rss/search?q=%22Machine+Learning%22+AND+%28technology+OR+trend+OR+business+OR+academic%29&hl=en-US&gl=US&ceid=US:en"
    },
    {
        "topic": "Image Processing, Computer Vision Articles",
        "url": "https://news.google.com/rss/search?q=%28%22Image+Processing%22+OR+%22Computer+Vision%22%29+AND+%28technology+OR+trend+OR+business+OR+academic%29&hl=en-US&gl=US&ceid=US:en"
    },
    {
        "topic": "AI, ML, CV, Image Processing Related Papers",
        "url": "https://news.google.com/rss/search?q=%28AI+OR+%22Machine+Learning%22+OR+%22Computer+Vision%22+OR+%22Image+Processing%22%29+AND+%28paper+OR+research+OR+study+OR+academic%29&hl=en-US&gl=US&ceid=US:en"
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

