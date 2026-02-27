import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def format_news_html(news_items):
    """
    Formats the list of news dictionaries into an HTML string, grouped by topic.
    """
    html_content = f"""
    <html>
      <head>
        <style>
          body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; line-height: 1.6; color: #e0e0e0; background-color: #121212; padding: 20px; }}
          .container {{ max-width: 800px; margin: 0 auto; background-color: #1e1e1e; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.5); }}
          .header {{ background: linear-gradient(135deg, #0d1b2a 0%, #1b263b 100%); color: #ffffff; padding: 30px 20px; text-align: center; border-bottom: 2px solid #415a77; }}
          .header h2 {{ margin: 0; font-size: 24px; letter-spacing: 1px; color: #e0e4cc; }}
          .header p {{ margin: 10px 0 0; font-size: 14px; color: #a0a0a0; }}
          .content {{ padding: 20px 30px; }}
          .topic-header {{ background-color: #2c3e50; color: #ecf0f1; padding: 12px 20px; margin: 30px 0 20px; border-left: 5px solid #3498db; border-radius: 0 4px 4px 0; font-size: 20px; }}
          .news-item {{ margin-bottom: 25px; padding-bottom: 25px; border-bottom: 1px solid #333333; }}
          .news-item:last-child {{ border-bottom: none; }}
          
          .dual-title {{ margin-bottom: 12px; }}
          .news-title-en {{ font-size: 18px; font-weight: 700; color: #6db3f2; margin-bottom: 4px; line-height: 1.3; }}
          .news-title-ko {{ font-size: 16px; font-weight: 600; color: #d0d0d0; margin-bottom: 0; line-height: 1.4; }}
          
          .news-date {{ font-size: 12px; color: #888888; margin-bottom: 15px; font-style: italic; }}
          
          .dual-summary {{ background-color: #252525; padding: 15px; border-radius: 6px; border: 1px solid #333333; font-size: 14px; color: #cccccc; line-height: 1.5; }}
          .summary-en {{ margin-bottom: 12px; }}
          .summary-ko {{ color: #cccccc; border-top: 1px dashed #555555; padding-top: 10px; margin-top: 10px; }}
          
          .news-link {{ display: inline-block; margin-top: 15px; padding: 8px 15px; background-color: #3498db; color: #ffffff !important; text-decoration: none; border-radius: 4px; font-size: 13px; font-weight: bold; transition: background-color 0.3s; }}
          .news-link:hover {{ background-color: #2980b9; }}
        </style>
      </head>
      <body>
        <div class="container">
            <div class="header">
              <h2>[Share]Daily AI & ML News Auto Mailing</h2>
              <p>{datetime.now().strftime("%Y년 %m월 %d일")}</p>
            </div>
            <div class="content">
    """
    
    if not news_items:
        html_content += "<p style='text-align:center;'>No news found for today.</p>"
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
                    <a class="news-link" href="{item['link']}" target="_blank">Read Full Article / Paper</a>
                </div>
                """
            
    html_content += """
            </div>
        </div>
      </body>
    </html>
    """
    return html_content

def send_email(subject, news_items):
    """
    Formats the news and sends an email via SMTP.
    Returns True if successful, False otherwise.
    """
    # Check if we have credentials
    if not config.SENDER_EMAIL or not config.SENDER_PASSWORD or not config.RECEIVER_EMAIL:
        logger.error("Email credentials are not fully set in the .env file. Skipping email send.")
        return False
        
    if not news_items:
        logger.warning("No news items to send.")
        return False
    
    try:
        html_body = format_news_html(news_items)
        
        msg = MIMEMultipart()
        msg['From'] = config.SENDER_EMAIL
        
        # Collect all recipients
        recipients = [config.RECEIVER_EMAIL]
        if config.FORWARD_EMAIL:
            recipients.append(config.FORWARD_EMAIL)
    except Exception as e:
        logger.error(f"Error preparing email: {e}")
        return False
        
    try:
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        
        logger.info(f"Connecting to SMTP server {config.SMTP_SERVER}:{config.SMTP_PORT}...")
        server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=10)
        server.starttls()  # Secure the connection
        server.login(config.SENDER_EMAIL, config.SENDER_PASSWORD)
        
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
        {"title": "Test AI Breakthrough", "link": "https://example.com", "published_date": "Today"}
    ]
    print(format_news_html(test_news))
