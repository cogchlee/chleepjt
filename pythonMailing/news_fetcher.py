import feedparser
import config
from bs4 import BeautifulSoup
from googletrans import Translator
import time
import requests
import re
import logging
from googlenewsdecoder import new_decoderv1
from newspaper import Article

logger = logging.getLogger(__name__)
translator = Translator()

def translate_to_korean(text):
    """
    Translates English text to Korean.
    Returns empty string if translation fails.
    """
    if not text:
        return ""
    try:
        translated = translator.translate(text, src='en', dest='ko')
        return translated.text
    except requests.exceptions.Timeout:
        logger.warning(f"Translation timeout for text: {text[:50]}...")
        return ""
    except requests.exceptions.ConnectionError:
        logger.warning("Translation service connection error.")
        return ""
    except Exception as e:
        logger.error(f"Translation error: {type(e).__name__}: {e}")
        return ""

def clean_html_summary(html_content, max_sentences=4):
    """
    Strips HTML tags to provide a clean text summary.
    Limits the output to a maximum of `max_sentences` sentences.
    """
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=' ').strip()
    
    if len(text) < 20: 
        return text

    sentences = re.split(r'(?<=[.!?]) +', text.replace("\n", " "))
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return ""
    
    limited_text = ' '.join(sentences[:max_sentences])
    if len(sentences) > max_sentences:
        limited_text += "..."
        
    return limited_text

def extract_article_summary(url, fallback_html, max_sentences=4):
    """
    Attempts to decode the Google News URL and fetch the actual article text.
    Uses Newspaper3k to parse the text. If it fails, falls back to the RSS html summary.
    """
    try:
        # Give googlenewsdecoder a small break to avoid 429 Too Many Requests
        time.sleep(1)
        decoded = new_decoderv1(url)
        if hasattr(decoded, "get"):
            real_url = decoded.get("decoded_url")
        else:
            real_url = decoded.get("decoded_url") if isinstance(decoded, dict) else url
            
        if real_url:
            article = Article(real_url)
            article.download()
            article.parse()
            if article.text and len(article.text) > 100:
                return clean_html_summary(article.text, max_sentences)
                
    except requests.exceptions.RequestException as e:
        logger.warning(f"    -> Network error extracting article: {type(e).__name__}: {e}")
    except Exception as e:
        logger.warning(f"    -> Article extraction failed ({e}), falling back to RSS summary.")
        
    return clean_html_summary(fallback_html, max_sentences)

def check_link_validity(url):
    """
    Checks if a URL is reachable.
    Returns False if unreachable or timeout.
    """
    try:
        response = requests.head(url, timeout=5, allow_redirects=True, 
                               headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code >= 400:
            response = requests.get(url, timeout=5, stream=True, 
                                  headers={'User-Agent': 'Mozilla/5.0'})
        return response.status_code < 400
    except requests.exceptions.Timeout:
        logger.debug(f"Link check timeout for {url}")
        return False
    except requests.exceptions.ConnectionError:
        logger.debug(f"Connection error checking {url}")
        return False
    except Exception as e:
        logger.debug(f"Error checking link {url}: {type(e).__name__}")
        return False

def fetch_latest_ai_news(limit=2):
    """
    Fetches the latest AI news from all configured RSS feeds.
    Verifies the link works before including it.
    
    Args:
        limit (int, optional): The maximum number of news articles to return per topic. Defaults to 2.
        
    Returns:
        list of dict: A list containing dictionaries with bilingual titles and summaries.
    """
    news_items = []
    
    for feed_info in config.RSS_FEEDS:
        topic = feed_info["topic"]
        url = feed_info["url"]
        logger.info(f"Fetching news for topic: {topic}")
        
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.error(f"Failed to fetch feed for {topic}: {e}")
            continue
        
        valid_items_for_topic = 0
        
        try:
            for entry in feed.entries:
                if valid_items_for_topic >= limit:
                    break
                    
                try:
                    title_en = entry.title
                    link = entry.link
                    
                    # Verify the link works
                    logger.debug(f"Checking link validity: {link[:50]}...")
                    if not check_link_validity(link):
                        logger.debug(f"Link unreachable: {link}")
                        continue
                    
                    published = entry.get('published', 'N/A')
                    summary_html = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                    
                    # Fetch the real article text for a proper summary
                    logger.debug(f"Extracting summary for: {title_en[:30]}...")
                    summary_en = extract_article_summary(link, summary_html)
                    
                    if not summary_en or len(summary_en) < 20:
                        summary_en = clean_html_summary(summary_html)
                    
                    # Translate to Korean
                    logger.debug(f"Translating: {title_en[:30]}...")
                    title_ko = translate_to_korean(title_en)
                    summary_ko = translate_to_korean(summary_en)
                    time.sleep(0.5)
                    
                    news_items.append({
                        "topic": topic,
                        "title_en": title_en,
                        "title_ko": title_ko,
                        "link": link,
                        "published_date": published,
                        "summary_en": summary_en,
                        "summary_ko": summary_ko
                    })
                    valid_items_for_topic += 1
                    logger.info(f"Added article: {title_en[:50]}...")
                    
                    time.sleep(1)
                    
                except (AttributeError, KeyError) as e:
                    logger.warning(f"Error parsing feed entry: {e}")
                    continue
        except AttributeError as e:
            logger.error(f"Error processing feed entries for {topic}: {e}")
        
    logger.info(f"Total news items fetched: {len(news_items)}")
    return news_items

if __name__ == "__main__":
    news = fetch_latest_ai_news(2)
    for index, item in enumerate(news, 1):
        print(f"[{item['topic']}] {item['title_en']}")
        print(f"  KO: {item['title_ko']}")
        print(f"  Summary EN: {item['summary_en'][:100]}...")
        print(f"  Summary KO: {item['summary_ko'][:100]}...\n")
