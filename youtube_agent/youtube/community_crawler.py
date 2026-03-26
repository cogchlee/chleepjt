"""
youtube/community_crawler.py
============================
YouTube 커뮤니티 탭 게시글 Selenium 크롤러.

- YouTube Data API v3는 커뮤니티 게시글(Post)을 지원하지 않음
- Playwright 대신 Selenium을 사용 (Playwright는 Phase 5 자동화용으로 예약)
- Headless Chrome + 실제 User-Agent로 봇 탐지 회피
- cookies.json 파일로 인증된 세션 재사용 (로그인 유지)
- WebDriverWait 기반 안정적 요소 대기
"""

from __future__ import annotations

import json
import sys
import time
import random
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from youtube.models import ContentItem

# ── Selenium 임포트 (미설치 시 명확한 안내) ──
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        WebDriverException,
    )
    _SELENIUM_AVAILABLE = True
except ImportError:
    _SELENIUM_AVAILABLE = False

# 실제 Chrome User-Agent (봇 감지 회피용)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# 커뮤니티 탭 관련 설정
_COMMUNITY_TAB_URL = "https://www.youtube.com/@{handle}/community"
_CHANNEL_ID_URL = "https://www.youtube.com/channel/{channel_id}/community"
_ELEMENT_WAIT_SEC = 15
_SCROLL_PAUSE_SEC = 2.0
_MAX_SCROLLS = 5  # 무한 스크롤 제한


class CommunityCrawler:
    """
    YouTube 커뮤니티 탭 게시글 크롤러.

    Args:
        cookies_path: 로그인 세션 쿠키 JSON 파일 경로 (선택).
                      없으면 비로그인 상태로 접근 (일부 게시글 접근 불가).
        headless:     True = 화면 없이 실행 (서버 환경).
        chromedriver_path: chromedriver 실행 파일 경로 (None = PATH에서 자동 탐색).
    """

    def __init__(
        self,
        cookies_path: str | Path | None = None,
        headless: bool = True,
        chromedriver_path: str | None = None,
    ):
        if not _SELENIUM_AVAILABLE:
            raise ImportError(
                "selenium이 설치되지 않았습니다. "
                "pip install selenium 을 실행하세요."
            )
        self.cookies_path = Path(cookies_path) if cookies_path else None
        self.headless = headless
        self.chromedriver_path = chromedriver_path
        self._driver: Optional["webdriver.Chrome"] = None

    # ──────────────────────────────────────────────
    # Driver 생명주기
    # ──────────────────────────────────────────────

    def _build_options(self) -> "Options":
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")          # Chrome 112+ 새 headless
        options.add_argument(f"--user-agent={_USER_AGENT}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=ko-KR")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        return options

    def start(self) -> None:
        """WebDriver를 시작한다."""
        options = self._build_options()
        service = (
            Service(self.chromedriver_path)
            if self.chromedriver_path
            else Service()
        )
        self._driver = webdriver.Chrome(service=service, options=options)
        # navigator.webdriver 속성 숨기기 (봇 감지 회피)
        self._driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )

    def stop(self) -> None:
        """WebDriver를 종료한다."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    # ──────────────────────────────────────────────
    # 쿠키 로드 (인증 세션 재사용)
    # ──────────────────────────────────────────────

    def _load_cookies(self) -> bool:
        """
        cookies.json에서 쿠키를 로드해 드라이버에 주입한다.

        cookies.json 형식 (EditThisCookie 또는 browser 내보내기 형식):
        [{"name": "...", "value": "...", "domain": ".youtube.com", ...}, ...]

        Returns:
            True = 쿠키 로드 성공
        """
        if not self.cookies_path or not self.cookies_path.exists():
            return False
        try:
            cookies = json.loads(self.cookies_path.read_text(encoding="utf-8"))
            # 쿠키 주입 전 해당 도메인을 먼저 방문해야 함
            self._driver.get("https://www.youtube.com")
            time.sleep(2)
            for cookie in cookies:
                # Selenium이 요구하는 필드만 필터링
                clean = {
                    k: v for k, v in cookie.items()
                    if k in ("name", "value", "domain", "path", "secure", "expiry")
                }
                try:
                    self._driver.add_cookie(clean)
                except Exception:
                    pass  # 일부 쿠키 실패 무시
            return True
        except Exception as e:
            print(f"[CommunityCrawler] 쿠키 로드 실패: {e}")
            return False

    # ──────────────────────────────────────────────
    # 커뮤니티 탭 수집
    # ──────────────────────────────────────────────

    def fetch_community_posts(
        self,
        channel_id: str,
        max_posts: int = 10,
    ) -> list[ContentItem]:
        """
        지정 채널의 커뮤니티 게시글을 수집한다.

        Args:
            channel_id: 대상 채널 ID (UC로 시작)
            max_posts:  최대 수집 게시글 수

        Returns:
            ContentItem(content_type='community') 리스트
        """
        if not self._driver:
            raise RuntimeError("start()를 먼저 호출하세요.")

        url = _CHANNEL_ID_URL.format(channel_id=channel_id)
        results: list[ContentItem] = []

        try:
            # 쿠키 로드 (최초 1회)
            cookie_loaded = self._load_cookies()
            if cookie_loaded:
                print(f"[CommunityCrawler] 인증 쿠키 로드 완료.")

            # 커뮤니티 탭으로 이동
            self._driver.get(url)
            _random_delay(1.5, 3.0)

            # 커뮤니티 탭 존재 확인
            try:
                WebDriverWait(self._driver, _ELEMENT_WAIT_SEC).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "ytd-backstage-post-renderer")
                    )
                )
            except TimeoutException:
                print(f"[CommunityCrawler] 커뮤니티 탭 미존재 또는 로드 실패: {channel_id}")
                return []

            # 스크롤하며 게시글 수집
            for _ in range(_MAX_SCROLLS):
                posts = self._driver.find_elements(
                    By.CSS_SELECTOR, "ytd-backstage-post-renderer"
                )
                if len(posts) >= max_posts:
                    break
                self._driver.execute_script(
                    "window.scrollTo(0, document.documentElement.scrollHeight);"
                )
                _random_delay(_SCROLL_PAUSE_SEC, _SCROLL_PAUSE_SEC + 1)

            posts = self._driver.find_elements(
                By.CSS_SELECTOR, "ytd-backstage-post-renderer"
            )[:max_posts]

            for post in posts:
                item = self._parse_post(post, channel_id)
                if item:
                    results.append(item)

        except WebDriverException as e:
            print(f"[CommunityCrawler] WebDriver 오류: {e}")
        except Exception as e:
            print(f"[CommunityCrawler] 예상치 못한 오류: {e}")

        return results

    def _parse_post(
        self, post_element, channel_id: str
    ) -> Optional[ContentItem]:
        """단일 게시글 요소를 파싱해 ContentItem으로 변환한다."""
        try:
            # 게시글 ID (URL에서 추출)
            post_id = ""
            try:
                time_el = post_element.find_element(
                    By.CSS_SELECTOR, "yt-formatted-string#published-time-text a"
                )
                href = time_el.get_attribute("href") or ""
                # URL 형식: .../post/UgkxXXXXXX
                post_id = href.split("/post/")[-1].split("?")[0] if "/post/" in href else ""
                published_at = time_el.text or ""
                post_url = href if href.startswith("http") else f"https://www.youtube.com{href}"
            except NoSuchElementException:
                return None

            if not post_id:
                return None

            # 본문 텍스트
            try:
                content_el = post_element.find_element(
                    By.CSS_SELECTOR, "yt-formatted-string#content-text"
                )
                title = content_el.text[:200]  # 200자로 제한
            except NoSuchElementException:
                title = "(이미지/미디어 게시글)"

            return ContentItem(
                content_id=post_id,
                content_type="community",
                channel_id=channel_id,
                title=title,
                url=post_url,
                published_at=published_at,  # 상대 시각 문자열 (ex: "3일 전")
            )
        except Exception as e:
            print(f"[CommunityCrawler] 게시글 파싱 오류: {e}")
            return None


def _random_delay(min_sec: float, max_sec: float) -> None:
    """봇 탐지 회피를 위한 랜덤 대기."""
    time.sleep(random.uniform(min_sec, max_sec))


# ── 직접 실행 테스트 ──
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("channel_id", help="채널 ID (UC...)")
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--cookies", default="./data/cookies.json")
    args = parser.parse_args()

    print(f"커뮤니티 탭 수집 테스트: {args.channel_id}")
    with CommunityCrawler(
        cookies_path=args.cookies,
        headless=not args.no_headless,
    ) as crawler:
        posts = crawler.fetch_community_posts(args.channel_id, max_posts=5)

    print(f"\n수집된 게시글 수: {len(posts)}")
    for p in posts:
        print(f"  {p}")
