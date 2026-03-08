import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")

def send_lottery_email(subject, html_content):
    """
    Sends an HTML formatted email containing lottery predictions or triple luck recommendations.
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
        logger.error("Missing email credentials in .env. Cannot send email.")
        return False

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    
    # Prepend dynamic timestamp
    body = f"<p><strong>Generated Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
    body += html_content

    msg.attach(MIMEText(body, 'html'))

    try:
        logger.info(f"Attempting to send email '{subject}' to {RECEIVER_EMAIL}...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        logger.info("Email sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
