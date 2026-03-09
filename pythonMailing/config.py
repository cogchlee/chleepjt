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
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "ai_news_mailing.log")),
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

# Schedule Configuration
SCHEDULE_TYPE = os.getenv("SCHEDULE_TYPE", "once_daily")
CAT2_SCHEDULE_TYPE = os.getenv("CAT2_SCHEDULE_TYPE", "once_daily")

# Category 2 Configuration
# If CAT2 specific credentials are not provided, it falls back to the base credentials to avoid duplication.
CAT2_SENDER_EMAIL = os.getenv("CAT2_SENDER_EMAIL", SENDER_EMAIL)
CAT2_SENDER_PASSWORD = os.getenv("CAT2_SENDER_PASSWORD", SENDER_PASSWORD)
CAT2_RECEIVER_EMAIL = os.getenv("CAT2_RECEIVER_EMAIL", RECEIVER_EMAIL)
CAT2_FORWARD_EMAIL = os.getenv("CAT2_FORWARD_EMAIL", FORWARD_EMAIL)

# Categories definition
CATEGORIES = [
    {
        "id": "cat1",
        "name": "AI & ML",
        "email_subject_prefix": "[Share] Daily AI & ML News Auto Mailing",
        "schedule_type": SCHEDULE_TYPE,
        "credentials": {
            "SENDER_EMAIL": SENDER_EMAIL,
            "SENDER_PASSWORD": SENDER_PASSWORD,
            "RECEIVER_EMAIL": RECEIVER_EMAIL,
            "FORWARD_EMAIL": FORWARD_EMAIL
        },
        "keywords_en": [
            "technology", "trend", "innovation", "breakthrough", "research",
            "development", "advance", "launch", "release", "analysis",
            "insight", "state-of-the-art", "cutting-edge", "impact", "future"
        ],
        "keywords_ko": [
            "기술", "동향", "혁신", "연구", "개발", "출시", "도입", "분석",
            "전망", "트렌드", "첨단", "미래", "성과", "논문", "활용"
        ],
        "feeds": [
            {
                "topic": "AI Agent, Tool, Assistant",
                "url_ko": "https://news.google.com/rss/search?q=AI+%28%EC%97%90%EC%9D%B4%EC%A0%84%ED%8A%B8+OR+%ED%88%B4+OR+%EC%96%B4%EC%8B%9C%EC%8A%A4%ED%84%B4%ED%8A%B8%29+AND+%28%EA%B8%B0%EC%88%A0+OR+%EB%8F%99%ED%96%A5+OR+%EC%82%AC%EC%97%85%29&hl=ko&gl=KR&ceid=KR:ko",
                "url_en": "https://news.google.com/rss/search?q=AI+%28Agent+OR+Tool+OR+Assistant%29+AND+%28technology+OR+trend+OR+business+OR+research%29&hl=en-US&gl=US&ceid=US:en"
            },
            {
                "topic": "AI and Machine Learning Research",
                "url_ko": "https://news.google.com/rss/search?q=%EB%A8%B8%EC%8B%A0%EB%9F%AC%EB%8B%9D+AND+%28%EA%B8%B0%EC%88%A0+OR+%EB%8F%99%ED%96%A5+OR+%EC%82%AC%EC%97%85+OR+%EC%97%B0%EA%B5%AC%29&hl=ko&gl=KR&ceid=KR:ko",
                "url_en": "https://news.google.com/rss/search?q=%22Machine+Learning%22+AND+%28technology+OR+trend+OR+business+OR+academic%29&hl=en-US&gl=US&ceid=US:en"
            },
            {
                "topic": "Image Processing, Computer Vision",
                "url_ko": "https://news.google.com/rss/search?q=%28%EC%9D%B4%EB%AF%B8%EC%A7%80+%EC%B2%98%EB%A6%AC+OR+%EC%BB%B4%ED%93%A8%ED%84%B0+%EB%B9%84%EC%A0%84%29+AND+%28%EA%B8%B0%EC%88%A0+OR+%EB%8F%99%ED%96%A5+OR+%EC%82%AC%EC%97%85%29&hl=ko&gl=KR&ceid=KR:ko",
                "url_en": "https://news.google.com/rss/search?q=%28%22Image+Processing%22+OR+%22Computer+Vision%22%29+AND+%28technology+OR+trend+OR+business+OR+academic%29&hl=en-US&gl=US&ceid=US:en"
            },
            {
                "topic": "Computer Vision, Image Processing Research with AI",
                "url_ko": "https://news.google.com/rss/search?q=%28AI+OR+%EB%A8%B8%EC%8B%A0%EB%9F%AC%EB%8B%9D+OR+%EC%BB%B4%ED%93%A8%ED%84%B0%EB%B9%84%EC%A0%84+OR+%EC%9D%B4%EB%AF%B8%EC%A7%80%EC%B2%98%EB%A6%AC%29+AND+%28%EB%85%BC%EB%AC%B8+OR+%EC%97%B0%EA%B5%AC%29&hl=ko&gl=KR&ceid=KR:ko",
                "url_en": "https://news.google.com/rss/search?q=%28AI+OR+%22Machine+Learning%22+OR+%22Computer+Vision%22+OR+%22Image+Processing%22%29+AND+%28paper+OR+research+OR+study+OR+academic%29&hl=en-US&gl=US&ceid=US:en"
            }
        ]
    },
    {
        "id": "cat2",
        "name": "Education & Literacy",
        "email_subject_prefix": "[Share] Daily Education & Literacy News",
        "schedule_type": CAT2_SCHEDULE_TYPE,
        "credentials": {
            "SENDER_EMAIL": CAT2_SENDER_EMAIL,
            "SENDER_PASSWORD": CAT2_SENDER_PASSWORD,
            "RECEIVER_EMAIL": CAT2_RECEIVER_EMAIL,
            "FORWARD_EMAIL": CAT2_FORWARD_EMAIL
        },
        "keywords_en": [
            "early childhood", "preschool", "infant", "toddler",
            "literacy", "early reading", "child development", "parenting"
        ],
        "keywords_ko": [
            "영유아 교육", "영유아 문해력", "조기 교육", "유아동",
            "어린이집", "유치원", "아동 발달", "육아"
        ],
        "feeds": [
            {
                "topic": "Early Childhood Education",
                "url_ko": "https://news.google.com/rss/search?q=%EC%9C%A0%EC%95%84%EA%B5%90%EC%9C%A1+OR+%EC%98%81%EC%9C%A0%EC%95%84+%EB%B0%9C%EB%8B%AC&hl=ko&gl=KR&ceid=KR:ko",
                "url_en": "https://news.google.com/rss/search?q=%22early+childhood+education%22+OR+%22child+development%22&hl=en-US&gl=US&ceid=US:en"
            },
            {
                "topic": "Early Childhood Literacy & Reading",
                "url_ko": "https://news.google.com/rss/search?q=%EB%AC%B8%ED%95%B4%EB%A0%A5+OR+%EB%8F%85%EC%84%9C+%EA%B5%90%EC%9C%A1&hl=ko&gl=KR&ceid=KR:ko",
                "url_en": "https://news.google.com/rss/search?q=literacy+OR+%22reading+education%22+OR+%22children+reading%22&hl=en-US&gl=US&ceid=US:en"
            }
        ]
    }
]

# Persistent storage for deduplication
SENT_LINKS_FILE = os.path.join(os.path.dirname(__file__), "sent_links.json")

# Configuration Validation
def get_active_categories():
    """
    Returns a list of categories that have valid credentials (minimally SENDER and RECEIVER).
    """
    active = []
    for cat in CATEGORIES:
        creds = cat["credentials"]
        if creds["SENDER_EMAIL"] and creds["SENDER_PASSWORD"] and creds["RECEIVER_EMAIL"]:
            active.append(cat)
        else:
            logger.warning(f"Category '{cat['name']}' disabled due to missing credentials.")
    return active

# We will just warn if no categories are active.
active_cats = get_active_categories()
if not active_cats:
    logger.warning("No categories have complete required credentials (SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL).")
else:
    logger.info(f"Loaded {len(active_cats)} active categories.")
