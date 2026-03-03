import feedparser
import config
from bs4 import BeautifulSoup
from googletrans import Translator
import time
import requests
import re
import logging
import os
import json
from datetime import datetime
from googlenewsdecoder import new_decoderv1
from newspaper import Article

logger = logging.getLogger(__name__)
translator = Translator()

KO_PATTERN = re.compile(r'[\uAC00-\uD7A3]')

def load_sent_links():
    if not os.path.exists(config.SENT_LINKS_FILE):
        return set(), ""
    try:
        with open(config.SENT_LINKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        last_reset_date = data.get("date", "")
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if now.weekday() == 6 and last_reset_date != today:
            logger.info("Weekly reset: It's Sunday. Clearing sent links tracker.")
            return set(), today
        return set(data.get("links", [])), last_reset_date
    except Exception as e:
        logger.error(f"Failed to load sent links: {e}")
        return set(), ""

def save_sent_links(links_set, last_reset_date):
    try:
        data = {
            "date": last_reset_date,
            "links": list(links_set)
        }
        with open(config.SENT_LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(links_set)} cumulative sent links to tracker (Last reset: {last_reset_date}).")
    except Exception as e:
        logger.error(f"Failed to save sent links: {e}")

def is_korean(text: str) -> bool:
    return bool(KO_PATTERN.search(text or ""))

def _score_article(title: str, summary: str, keywords_ko: list, keywords_en: list) -> int:
    combined = (title or "").lower()
    summary_text = (summary or "").lower()

    keywords = keywords_ko if is_korean(title) else keywords_en

    score = 0
    for kw in keywords:
        score += combined.count(kw.lower()) * 3
        score += summary_text.count(kw.lower())
    return score

def translate_text(text: str, src: str, dest: str) -> str:
    if not text:
        return ""
    try:
        result = translator.translate(text, src=src, dest=dest)
        return result.text
    except Exception as e:
        logger.error(f"Translation error ({src}->{dest}): {type(e).__name__}: {e}")
        return ""

def translate_to_korean(text: str) -> str:
    return translate_text(text, src='en', dest='ko')

def translate_to_english(text: str) -> str:
    return translate_text(text, src='ko', dest='en')

def clean_html_summary(html_content, max_sentences=4):
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
    limited = ' '.join(sentences[:max_sentences])
    if len(sentences) > max_sentences:
        limited += "..."
    return limited

def extract_article_summary(url, fallback_html, max_sentences=4):
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
        logger.warning(f"    -> Network error: {type(e).__name__}: {e}")
    except Exception as e:
        logger.warning(f"    -> Extraction failed ({e}), using RSS summary.")
    return clean_html_summary(fallback_html, max_sentences)

def check_link_validity(url):
    try:
        response = requests.head(url, timeout=5, allow_redirects=True,
                                 headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code >= 400:
            response = requests.get(url, timeout=5, stream=True,
                                    headers={'User-Agent': 'Mozilla/5.0'})
        return response.status_code < 400
    except Exception as e:
        logger.debug(f"Link check failed {url}: {type(e).__name__}")
        return False

def _fetch_candidates(url: str, limit: int, topic: str, sent_links: set) -> list:
    candidates = []
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        logger.error(f"Failed to parse feed {url}: {e}")
        return candidates

    for entry in feed.entries:
        if len(candidates) >= limit:
            break
        try:
            title_raw = entry.title
            link = entry.link

            if link in sent_links:
                continue

            if not check_link_validity(link):
                continue

            published = entry.get('published', 'N/A')
            summary_html = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            summary_raw = extract_article_summary(link, summary_html)
            if not summary_raw or len(summary_raw) < 20:
                summary_raw = clean_html_summary(summary_html)

            candidates.append({
                "topic": topic,
                "title_raw": title_raw,
                "summary_raw": summary_raw,
                "link": link,
                "published_date": published,
            })
            time.sleep(1)
        except (AttributeError, KeyError) as e:
            logger.warning(f"Entry parse error: {e}")
            continue

    return candidates

def _pick_best(candidates: list, keywords_ko: list, keywords_en: list) -> dict | None:
    if not candidates:
        return None
    scored = sorted(
        candidates,
        key=lambda c: _score_article(c["title_raw"], c["summary_raw"], keywords_ko, keywords_en),
        reverse=True
    )
    best = scored[0]
    best_score = _score_article(best['title_raw'], best['summary_raw'], keywords_ko, keywords_en)
    logger.info(f"  Best article (score={best_score}): {best['title_raw'][:60]}...")
    return best

def _build_bilingual(candidate: dict) -> dict:
    title_raw   = candidate["title_raw"]
    summary_raw = candidate["summary_raw"]

    if is_korean(title_raw):
        title_ko   = title_raw
        summary_ko = summary_raw
        logger.debug(f"  [KO->EN] Translating: {title_ko[:30]}...")
        title_en   = translate_to_english(title_ko) or title_ko
        summary_en = translate_to_english(summary_ko) if summary_ko else ""
    else:
        title_en   = title_raw
        summary_en = summary_raw
        logger.debug(f"  [EN->KO] Translating: {title_en[:30]}...")
        title_ko   = translate_to_korean(title_en) or title_en
        summary_ko = translate_to_korean(summary_en) if summary_en else ""

    time.sleep(0.5)

    return {
        "topic":        candidate["topic"],
        "title_en":     title_en,
        "title_ko":     title_ko,
        "link":         candidate["link"],
        "published_date": candidate["published_date"],
        "summary_en":   summary_en,
        "summary_ko":   summary_ko,
    }

def fetch_news_for_category(category_config: dict, candidate_pool: int = 10):
    news_items = []
    sent_links, last_reset_date = load_sent_links()
    
    current_iteration_links = set()
    
    keywords_en = category_config.get("keywords_en", [])
    keywords_ko = category_config.get("keywords_ko", [])

    for feed_info in category_config.get("feeds", []):
        topic  = feed_info["topic"]
        url_ko = feed_info.get("url_ko", "")
        url_en = feed_info.get("url_en", feed_info.get("url", ""))

        logger.info(f"--- Topic: {topic} ---")

        if url_ko:
            logger.info(f"  Fetching {candidate_pool} KO candidates (skipping duplicates)...")
            ko_candidates = _fetch_candidates(url_ko, candidate_pool, topic, sent_links.union(current_iteration_links))
            logger.info(f"  {len(ko_candidates)} KO candidates collected.")
            best_ko = _pick_best(ko_candidates, keywords_ko, keywords_en)
            if best_ko:
                news_items.append(_build_bilingual(best_ko))
                current_iteration_links.add(best_ko["link"])

        if url_en:
            logger.info(f"  Fetching {candidate_pool} EN candidates (skipping duplicates)...")
            en_candidates = _fetch_candidates(url_en, candidate_pool, topic, sent_links.union(current_iteration_links))
            logger.info(f"  {len(en_candidates)} EN candidates collected.")
            best_en = _pick_best(en_candidates, keywords_ko, keywords_en)
            if best_en:
                news_items.append(_build_bilingual(best_en))
                current_iteration_links.add(best_en["link"])

    if news_items:
        sent_links.update(current_iteration_links)
        save_sent_links(sent_links, last_reset_date)

    logger.info(f"Total articles selected for {category_config.get('name')}: {len(news_items)}")
    return news_items
