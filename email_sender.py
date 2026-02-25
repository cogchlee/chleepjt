import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config
from datetime import datetime

def format_news_html(news_items):
    """
    Formats the list of news dictionaries into an HTML string, grouped by topic.
    """
    html_content = f"""
    <html>
      <head>
        <style>
          body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }}
          .container {{ max-width: 800px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
          .header {{ background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: white; padding: 30px 20px; text-align: center; }}
          .header h2 {{ margin: 0; font-size: 24px; letter-spacing: 1px; }}
          .header p {{ margin: 10px 0 0; font-size: 14px; opacity: 0.8; }}
          .content {{ padding: 20px 30px; }}
          .topic-header {{ background-color: #f4f6f8; color: #2c3e50; padding: 12px 20px; margin: 30px 0 20px; border-left: 5px solid #2a5298; border-radius: 0 4px 4px 0; font-size: 20px; }}
          .news-item {{ margin-bottom: 25px; padding-bottom: 25px; border-bottom: 1px solid #eee; }}
          .news-item:last-child {{ border-bottom: none; }}
          
          .dual-title {{ margin-bottom: 12px; }}
          .news-title-en {{ font-size: 18px; font-weight: 700; color: #1a0dab; margin-bottom: 4px; line-height: 1.3; }}
          .news-title-ko {{ font-size: 16px; font-weight: 600; color: #444; margin-bottom: 0; line-height: 1.4; }}
          
          .news-date {{ font-size: 12px; color: #999; margin-bottom: 15px; font-style: italic; }}
          
          .dual-summary {{ background-color: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #eaeaea; font-size: 14px; color: #555; line-height: 1.5; }}
          .summary-en {{ margin-bottom: 12px; }}
          .summary-ko {{ color: #444; }}
          
          .news-link {{ display: inline-block; margin-top: 15px; padding: 8px 15px; background-color: #2a5298; color: white !important; text-decoration: none; border-radius: 4px; font-size: 13px; font-weight: bold; transition: background-color 0.3s; }}
          .news-link:hover {{ background-color: #1e3c72; }}
        </style>
      </head>
      <body>
        <div class="container">
            <div class="header">
              <h2>Daily AI & ML News Update 📰</h2>
              <p>{datetime.now().strftime("%B %d, %Y")}</p>
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
    """
    # Check if we have credentials
    if not config.SENDER_EMAIL or not config.SENDER_PASSWORD or not config.RECEIVER_EMAIL:
        print("Error: Email credentials are not fully set in the .env file. Skipping email send.")
        return False
        
    html_body = format_news_html(news_items)
    
    msg = MIMEMultipart()
    msg['From'] = config.SENDER_EMAIL
    
    # Collect all recipients
    recipients = [config.RECEIVER_EMAIL]
    if config.FORWARD_EMAIL:
        recipients.append(config.FORWARD_EMAIL)
        
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = subject
    
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        print(f"Connecting to SMTP server {config.SMTP_SERVER}:{config.SMTP_PORT}...")
        server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
        server.starttls()  # Secure the connection
        server.login(config.SENDER_EMAIL, config.SENDER_PASSWORD)
        
        print(f"Sending email to {', '.join(recipients)}...")
        server.send_message(msg)
        server.quit()
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Failed to send email. Error: {e}")
        return False

if __name__ == "__main__":
    # Test formatting only
    test_news = [
        {"title": "Test AI Breakthrough", "link": "https://example.com", "published_date": "Today"}
    ]
    print(format_news_html(test_news))
