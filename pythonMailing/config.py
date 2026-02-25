import os
from dotenv import load_dotenv

load_dotenv()

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
        "topic": "AI Agent, assistant, AI tool 관련 기사",
        "url": "https://news.google.com/rss/search?q=AI+%28Agent+OR+Assistant+OR+tools%29&hl=en-US&gl=US&ceid=US:en"
    },
    {
        "topic": "AI, Machine Learning, Image Processing, Computer Vision 관련 신규 기사 및 논문",
        "url": "https://news.google.com/rss/search?q=%28Machine+Learning+OR+Image+Processing+OR+Computer+Vision%29+AND+%28paper+OR+research+OR+article%29&hl=en-US&gl=US&ceid=US:en"
    }
]

# Schedule Configuration
# SCHEDULE_TYPE can be '10m' or 'twice_daily'
SCHEDULE_TYPE = os.getenv("SCHEDULE_TYPE", "twice_daily")

