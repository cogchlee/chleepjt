import feedparser
import config
from bs4 import BeautifulSoup
from googletrans import Translator
import time

translator = Translator()

def translate_to_korean(text):
    """
    Translates English text to Korean.
    """
    if not text:
        return ""
    try:
        translated = translator.translate(text, src='en', dest='ko')
        return translated.text
    except Exception as e:
        print(f"Translation error: {e}")
        return ""

def clean_html_summary(html_content, max_sentences=3):
    """
    Strips HTML tags to provide a clean text summary.
    Limits the output to a maximum of `max_sentences` sentences.
    """
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=' ').strip()
    
    # Split by common sentence terminators and take the first max_sentences
    import re
    sentences = re.split(r'(?<=[.!?]) +', text)
    limited_text = ' '.join(sentences[:max_sentences])
    if len(sentences) > max_sentences:
        limited_text += "..."
        
    return limited_text

def fetch_latest_ai_news(limit=10):
    """
    Fetches the latest AI news from all configured RSS feeds.
    
    Args:
        limit (int, optional): The maximum number of news articles to return per topic. Defaults to 10.
        
    Returns:
        list of dict: A list containing dictionaries with bilingual titles and summaries.
    """
    news_items = []
    
    for feed_info in config.RSS_FEEDS:
        topic = feed_info["topic"]
        url = feed_info["url"]
        print(f"Fetching news for topic: {topic}")
        
        feed = feedparser.parse(url)
        entries = feed.entries[:limit] if limit else feed.entries
        
        for entry in entries:
            title_en = entry.title
            link = entry.link
            published = entry.published
            
            summary_html = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            summary_en = clean_html_summary(summary_html)
            
            # Translate to Korean
            print(f"  Translating: {title_en[:30]}...")
            title_ko = translate_to_korean(title_en)
            summary_ko = translate_to_korean(summary_en)
            time.sleep(0.5) # Avoid hitting translation limits too fast
            
            news_items.append({
                "topic": topic,
                "title_en": title_en,
                "title_ko": title_ko,
                "link": link,
                "published_date": published,
                "summary_en": summary_en,
                "summary_ko": summary_ko
            })
        
    return news_items

if __name__ == "__main__":
    # Test the fetcher separately
    news = fetch_latest_ai_news(2)
    for index, item in enumerate(news, 1):
        print(f"[{item['topic']}] {item['title_en']}")
        print(f"  KO: {item['title_ko']}")
        print(f"  Summary EN: {item['summary_en'][:100]}...")
        print(f"  Summary KO: {item['summary_ko'][:100]}...\n")
