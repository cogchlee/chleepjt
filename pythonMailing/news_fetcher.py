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

# --------------------------------------------------------------------------
# Keywords used to score articles by technology/trend importance
# --------------------------------------------------------------------------
SCORE_KEYWORDS_EN = [
    "technology", "trend", "innovation", "breakthrough", "research",
    "development", "advance", "launch", "release", "analysis",
    "insight", "state-of-the-art", "cutting-edge", "impact", "future"
]
SCORE_KEYWORDS_KO = [
    "기술", "동향", "혁신", "연구", "개발", "출시", "도입", "분석",
    "전망", "트렌드", "첨단", "미래", "성과", "논문", "활용"
]

def is_korean(text: str) -> bool:
    return bool(KO_PATTERN.search(text or ""))

def _score_article(title: str, summary: str) -> int:
    """
    Scores an article by counting technology/trend keywords in title + summary.
    Title matches are weighted 3x, summary matches 1x.
    """
    combined = (title or "").lower()
    summary_text = (summary or "").lower()

    keywords = SCORE_KEYWORDS_KO if is_korean(title) else SCORE_KEYWORDS_EN

    score = 0
    for kw in keywords:
        score += combined.count(kw) * 3
        score += summary_text.count(kw)
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

def _fetch_candidates(url: str, limit: int, topic: str) -> list:
    """
    Fetch up to `limit` valid articles from one RSS feed.
    Returns a list of raw article dicts (title, summary, link, published).
    Does NOT translate yet – translation happens only on the winner.
    """
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

def _pick_best(candidates: list) -> dict | None:
    """
    Score all candidates and return the one with the highest
    technology/trend importance score.
    """
    if not candidates:
        return None
    scored = sorted(
        candidates,
        key=lambda c: _score_article(c["title_raw"], c["summary_raw"]),
        reverse=True
    )
    best = scored[0]
    logger.info(f"  Best article (score={_score_article(best['title_raw'], best['summary_raw'])}): "
                f"{best['title_raw'][:60]}...")
    return best

def _build_bilingual(candidate: dict) -> dict:
    """
    Translate the winning candidate into both languages and return
    the final bilingual article dict.
    """
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

def fetch_latest_ai_news(candidate_pool: int = 10):
    """
    For each topic:
      1. Fetch up to `candidate_pool` Korean articles from url_ko.
      2. Fetch up to `candidate_pool` English articles from url_en.
      3. Score each pool by technology/trend keyword importance.
      4. Pick the TOP-1 Korean article and TOP-1 English article.
      5. Translate only those two winners.

    Result: 4 topics × (1 KO + 1 EN) = 8 articles total.
    """
    news_items = []

    for feed_info in config.RSS_FEEDS:
        topic  = feed_info["topic"]
        url_ko = feed_info.get("url_ko", "")
        url_en = feed_info.get("url_en", feed_info.get("url", ""))

        logger.info(f"--- Topic: {topic} ---")

        # ----- Korean pool → best 1 -----
        if url_ko:
            logger.info(f"  Fetching {candidate_pool} KO candidates...")
            ko_candidates = _fetch_candidates(url_ko, candidate_pool, topic)
            logger.info(f"  {len(ko_candidates)} KO candidates collected.")
            best_ko = _pick_best(ko_candidates)
            if best_ko:
                news_items.append(_build_bilingual(best_ko))

        # ----- English pool → best 1 -----
        if url_en:
            logger.info(f"  Fetching {candidate_pool} EN candidates...")
            en_candidates = _fetch_candidates(url_en, candidate_pool, topic)
            logger.info(f"  {len(en_candidates)} EN candidates collected.")
            best_en = _pick_best(en_candidates)
            if best_en:
                news_items.append(_build_bilingual(best_en))

    logger.info(f"Total articles selected: {len(news_items)}")
    return news_items

if __name__ == "__main__":
    news = fetch_latest_ai_news()
    for item in news:
        print(f"\n[{item['topic']}]")
        print(f"  KO: {item['title_ko']}")
        print(f"  EN: {item['title_en']}")
        print(f"  KO Summary: {item['summary_ko'][:80]}...")
        print(f"  EN Summary: {item['summary_en'][:80]}...")
