import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def format_news_html(news_items, header_title):
    """
    Formats the list of news dictionaries into an HTML string, grouped by topic.
    """
    html_content = f"""
    <html>
      <head>
        <style>
          body {{ font-family: 'Pretendard', 'Apple SD Gothic Neo', 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #F9FAFB; background-color: #0B0D0F; padding: 20px; margin: 0; }}
          .container {{ max-width: 800px; margin: 0 auto; background-color: #191F28; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
          .header {{ padding: 40px 30px; text-align: center; border-bottom: 1px solid #333D4B; background-color: #191F28; }}
          .header h2 {{ margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.5px; color: #F9FAFB; }}
          .header p {{ margin: 12px 0 0; font-size: 15px; color: #8B95A1; }}
          .content {{ padding: 20px 30px 40px; }}
          .topic-header {{ color: #3182F6; padding: 20px 0 10px; margin: 20px 0 10px; border-bottom: 2px solid #333D4B; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }}
          .news-item {{ background-color: #222831; border-radius: 16px; padding: 24px; margin-bottom: 20px; }}
          
          .dual-title {{ margin-bottom: 14px; }}
          .news-title-en {{ font-size: 18px; font-weight: 700; color: #F9FAFB; margin-bottom: 8px; line-height: 1.4; letter-spacing: -0.3px; word-break: keep-all; }}
          .news-title-ko {{ font-size: 16px; font-weight: 600; color: #B0B8C1; margin-bottom: 0; line-height: 1.5; letter-spacing: -0.3px; word-break: keep-all; }}
          
          .news-date {{ font-size: 13px; color: #8B95A1; margin-bottom: 16px; font-weight: 500; display: inline-block; background-color: #333D4B; padding: 4px 8px; border-radius: 6px; }}
          
          .dual-summary {{ background-color: #191F28; padding: 18px; border-radius: 12px; font-size: 15px; color: #D1D6DB; line-height: 1.6; letter-spacing: -0.2px; }}
          .summary-en {{ margin-bottom: 16px; word-break: keep-all; }}
          .summary-ko {{ color: #8B95A1; border-top: 1px solid #333D4B; padding-top: 16px; word-break: keep-all; }}
          
          .button-container {{ margin-top: 24px; text-align: right; }}
          .news-link {{ display: inline-block; padding: 12px 24px; background-color: #3182F6; color: #ffffff !important; text-decoration: none; border-radius: 12px; font-size: 15px; font-weight: 600; letter-spacing: -0.3px; }}
        </style>
      </head>
      <body>
        <div class="container">
            <div class="header">
              <h2>{header_title}</h2>
              <p>{datetime.now().strftime("%Y년 %m월 %d일")}</p>
            </div>
            <div class="content">
    """
    
    if not news_items:
        html_content += "<p style='text-align:center; color: #8B95A1; padding: 40px;'>No news found for today.</p>"
    else:
        # Group items by topic
        grouped_news = {}
        for item in news_items:
            grouped_news.setdefault(item['topic'], []).append(item)
            
        for topic, items in grouped_news.items():
            html_content += f'<h3 class="topic-header">{topic}</h3>'
            for item in items:
                html_content += f"""
                <div class="news-item">
                    <div class="dual-title">
                        <div class="news-title-en">{item['title_en']}</div>
                        <div class="news-title-ko">{item['title_ko']}</div>
                    </div>
                    <div class="news-date">Published: {item['published_date']}</div>
                    <div class="dual-summary">
                        <div class="summary-en">{item['summary_en']}</div>
                        <div class="summary-ko">{item['summary_ko']}</div>
                    </div>
                    <div class="button-container">
                        <a class="news-link" href="{item['link']}" target="_blank">Read Full Article</a>
                    </div>
                </div>
                """
            
    html_content += """
            </div>
        </div>
      </body>
    </html>
    """
    return html_content

def send_email(subject, news_items, credentials, header_title=None):
    """
    Formats the news and sends an email via SMTP.
    Returns True if successful, False otherwise.
    """
    smtp_server = credentials.get("SMTP_SERVER", config.SMTP_SERVER)
    smtp_port = int(credentials.get("SMTP_PORT", config.SMTP_PORT))
    sender_email = credentials.get("SENDER_EMAIL")
    sender_password = credentials.get("SENDER_PASSWORD")
    receiver_email = credentials.get("RECEIVER_EMAIL")
    forward_email = credentials.get("FORWARD_EMAIL")
    
    # Check if we have credentials
    if not sender_email or not sender_password or not receiver_email:
        logger.error("Email credentials are not fully set for this category. Skipping email send.")
        return False
        
    if not news_items:
        logger.warning("No news items to send.")
        return False
    
    try:
        html_body = format_news_html(news_items, header_title or subject)
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        
        # Collect all recipients
        recipients = [receiver_email]
        
        forward_clean = str(forward_email).strip().upper() if forward_email else ""
        if forward_clean and forward_clean != "NONE":
            kst_now = datetime.utcnow() + timedelta(hours=9)
            if kst_now.weekday() < 5:  # 0=Mon, ..., 4=Fri, 5=Sat, 6=Sun
                recipients.append(forward_email.strip())
            else:
                logger.info("It's the weekend (KST). Skipping FORWARD_EMAIL delivery.")
    except Exception as e:
        logger.error(f"Error preparing email: {e}")
        return False
        
    try:
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        
        logger.info(f"Connecting to SMTP server {smtp_server}:{smtp_port}...")
        
        # LG corporate servers / Outlook often use 587 with STARTTLS or 465 with SSL.
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            server.starttls()  # Secure the connection
            
        server.login(sender_email, sender_password)
        
        logger.info(f"Sending email to {', '.join(recipients)}...")
        server.send_message(msg)
        server.quit()
        logger.info("Email sent successfully!")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed. Check SENDER_EMAIL and SENDER_PASSWORD.")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error occurred: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email. Error: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    # Test formatting only
    test_news = [
        {"title_en": "Test English Title", "title_ko": "테스트 한글 제목", "link": "https://example.com", "published_date": "Today", "topic": "Test Topic", "summary_en": "English summary...", "summary_ko": "한글 요약..."}
    ]
    print(format_news_html(test_news, "[Share] Test Category News"))
