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

KO_PATTERN = re.compile(r'[\uAC00-\uD7A3]')

def is_korean(text: str) -> bool:
    """Returns True if text contains Korean characters."""
    return bool(KO_PATTERN.search(text or ""))

def translate_text(text: str, src: str, dest: str) -> str:
    """Generic translation helper. Returns empty string on failure."""
    if not text:
        return ""
    try:
        result = translator.translate(text, src=src, dest=dest)
        return result.text
    except requests.exceptions.Timeout:
        logger.warning(f"Translation timeout: {text[:50]}...")
        return ""
    except requests.exceptions.ConnectionError:
        logger.warning("Translation connection error.")
        return ""
    except Exception as e:
        logger.error(f"Translation error: {type(e).__name__}: {e}")
        return ""

def translate_to_korean(text: str) -> str:
    return translate_text(text, src='en', dest='ko')

def translate_to_english(text: str) -> str:
    return translate_text(text, src='ko', dest='en')

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
    Falls back to the RSS html summary on any error.
    """
    try:
        time.sleep(1)
        decoded = new_decoderv1(url)
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
    Checks if a URL is reachable. Returns False if unreachable or timeout.
    """
    try:
        response = requests.head(url, timeout=5, allow_redirects=True,
                               headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code >= 400:
            response = requests.get(url, timeout=5, stream=True,
                                  headers={'User-Agent': 'Mozilla/5.0'})
        return response.status_code < 400
    except Exception as e:
        logger.debug(f"Error checking link {url}: {type(e).__name__}")
        return False

def _fetch_articles_from_feed(url: str, limit: int, topic: str) -> list:
    """
    Internal helper: fetches up to `limit` valid articles from one RSS URL.
    Automatically detects language and sets title_ko / title_en accordingly.
    """
    items = []
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        logger.error(f"Failed to parse feed {url}: {e}")
        return items

    for entry in feed.entries:
        if len(items) >= limit:
            break
        try:
            title_raw = entry.title
            link = entry.link

            logger.debug(f"Checking link: {link[:60]}...")
            if not check_link_validity(link):
                logger.debug("Link unreachable – skipping.")
                continue

            published = entry.get('published', 'N/A')
            summary_html = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            summary_raw = extract_article_summary(link, summary_html)
            if not summary_raw or len(summary_raw) < 20:
                summary_raw = clean_html_summary(summary_html)

            # --- Language-aware bilingual handling ---
            if is_korean(title_raw):
                title_ko = title_raw
                summary_ko = summary_raw
                logger.debug(f"  [KO] Translating to EN: {title_ko[:30]}...")
                title_en = translate_to_english(title_ko) or title_ko
                summary_en = translate_to_english(summary_ko) if summary_ko else ""
            else:
                title_en = title_raw
                summary_en = summary_raw
                logger.debug(f"  [EN] Translating to KO: {title_en[:30]}...")
                title_ko = translate_to_korean(title_en) or title_en
                summary_ko = translate_to_korean(summary_en) if summary_en else ""

            time.sleep(0.5)

            items.append({
                "topic": topic,
                "title_en": title_en,
                "title_ko": title_ko,
                "link": link,
                "published_date": published,
                "summary_en": summary_en,
                "summary_ko": summary_ko
            })
            logger.info(f"Added article: {title_ko[:50] if title_ko else title_en[:50]}...")
            time.sleep(1)

        except (AttributeError, KeyError) as e:
            logger.warning(f"Error parsing entry: {e}")
            continue

    return items

def fetch_latest_ai_news(limit=2):
    """
    Fetches the latest AI news from all configured RSS feeds.
    Korean articles are prioritised; if not enough Korean articles are found,
    English articles are fetched as fallback.

    Args:
        limit (int): Max articles per topic. Defaults to 2.

    Returns:
        list of dict with bilingual titles and summaries.
    """
    news_items = []

    for feed_info in config.RSS_FEEDS:
        topic    = feed_info["topic"]
        url_ko   = feed_info.get("url_ko", "")
        url_en   = feed_info.get("url_en", feed_info.get("url", ""))

        logger.info(f"Fetching (KO priority) for topic: {topic}")

        # 1. Try Korean feed first
        ko_items = []
        if url_ko:
            ko_items = _fetch_articles_from_feed(url_ko, limit, topic)
            logger.info(f"  {len(ko_items)} KO article(s) fetched.")

        # 2. Fill remaining slots with English feed
        remaining = limit - len(ko_items)
        en_items = []
        if remaining > 0 and url_en:
            logger.info(f"  Fetching {remaining} more from EN feed as fallback...")
            en_items = _fetch_articles_from_feed(url_en, remaining, topic)
            logger.info(f"  {len(en_items)} EN article(s) added.")

        news_items.extend(ko_items + en_items)

    logger.info(f"Total news items fetched: {len(news_items)}")
    return news_items

if __name__ == "__main__":
    news = fetch_latest_ai_news(2)
    for item in news:
        print(f"[{item['topic']}]")
        print(f"  KO: {item['title_ko']}")
        print(f"  EN: {item['title_en']}")
        print(f"  Summary KO: {item['summary_ko'][:80]}...")
        print(f"  Summary EN: {item['summary_en'][:80]}...\n")
