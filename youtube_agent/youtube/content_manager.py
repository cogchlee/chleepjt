"""
youtube/content_manager.py
==========================
Phase 2 통합 파사드(Facade) — 요청 명세의 핵심 결과물.

사용 방법:
    from youtube.content_manager import ContentManager

    mgr = ContentManager(youtube_service=yt, db=db_mgr)
    candidates = mgr.discover_candidates(channel_id="UCxxxxxx")
    for item in candidates:
        print(item)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from youtube.client import YouTubeAPIClient
from youtube.community_crawler import CommunityCrawler, _SELENIUM_AVAILABLE
from youtube.filter import ContentFilter
from youtube.models import ContentItem
from db.database import DatabaseManager
from utils.logger import get_logger

log = get_logger("youtube_agent")


class ContentManager:
    """
    채널의 콘텐츠를 수집 → 필터링 → 후보군 반환하는 통합 매니저.

    Args:
        youtube_service:    googleapiclient 서비스 객체 (auth/oauth.py 결과)
        db:                 DatabaseManager 인스턴스
        max_videos:         채널당 최대 영상 수집 수 (기본 20)
        max_posts:          채널당 최대 커뮤니티 게시글 수집 수 (기본 10)
        include_community:  True = 커뮤니티 탭 크롤링 포함 (Selenium 필요)
        cookies_path:       Selenium 크롤러용 쿠키 JSON 경로
        headless:           Selenium headless 여부
    """

    def __init__(
        self,
        youtube_service,
        db: DatabaseManager,
        max_videos: int = 20,
        max_posts: int = 10,
        include_community: bool = True,
        cookies_path: str | Path | None = "./data/cookies.json",
        headless: bool = True,
    ):
        self._api = YouTubeAPIClient(youtube_service, max_results=max_videos)
        self._db = db
        self._filter = ContentFilter(db)
        self.max_posts = max_posts
        self.include_community = include_community
        self.cookies_path = cookies_path
        self.headless = headless

    # ──────────────────────────────────────────────
    # 공개 인터페이스
    # ──────────────────────────────────────────────

    def discover_candidates(
        self,
        channel_id: str,
    ) -> list[ContentItem]:
        """
        단일 채널에서 댓글 작성 후보 콘텐츠를 수집 및 반환한다.

        처리 순서:
          1. YouTube API → 동영상/쇼츠 수집
          2. (선택) Selenium → 커뮤니티 게시글 수집
          3. ContentFilter → 중복/처리완료 항목 제거
          4. 최종 후보 반환

        Returns:
            필터링된 ContentItem 리스트
        """
        log.info("[ContentManager] 채널 수집 시작: %s", channel_id)
        collected: list[ContentItem] = []

        # ── 1. 동영상 & 쇼츠 ──
        try:
            videos = self._api.fetch_recent_videos(channel_id)
            log.info(
                "[ContentManager] API 수집 완료 — 동영상/쇼츠: %d건", len(videos)
            )
            collected.extend(videos)
        except Exception as e:
            log.error("[ContentManager] API 수집 오류: %s", e, exc_info=True)

        # ── 2. 커뮤니티 게시글 (선택) ──
        if self.include_community:
            if not _SELENIUM_AVAILABLE:
                log.warning(
                    "[ContentManager] Selenium 미설치 — 커뮤니티 탭 수집 건너뜀. "
                    "'pip install selenium'을 실행하세요."
                )
            else:
                try:
                    with CommunityCrawler(
                        cookies_path=self.cookies_path,
                        headless=self.headless,
                    ) as crawler:
                        posts = crawler.fetch_community_posts(
                            channel_id, max_posts=self.max_posts
                        )
                    log.info(
                        "[ContentManager] 커뮤니티 수집 완료 — 게시글: %d건", len(posts)
                    )
                    collected.extend(posts)
                except Exception as e:
                    log.error(
                        "[ContentManager] 커뮤니티 수집 오류 (건너뜀): %s", e, exc_info=True
                    )

        # ── 3. 필터링 ──
        candidates = self._filter.filter_candidates(collected)
        stats = self._filter.get_filter_stats(collected, candidates)
        log.info(
            "[ContentManager] 필터링 완료 — 수집: %d건, 후보: %d건, 제외: %d건 "
            "(video=%d, short=%d, community=%d)",
            stats["original_count"],
            stats["candidate_count"],
            stats["filtered_out"],
            stats["types"]["video"],
            stats["types"]["short"],
            stats["types"]["community"],
        )

        return candidates

    def discover_all_channels(
        self,
        channel_ids: list[str],
    ) -> list[ContentItem]:
        """
        여러 채널에서 후보 콘텐츠를 수집한다.
        채널별 오류가 발생해도 다음 채널 처리를 계속한다.
        """
        all_candidates: list[ContentItem] = []
        for channel_id in channel_ids:
            try:
                candidates = self.discover_candidates(channel_id)
                all_candidates.extend(candidates)
            except Exception as e:
                log.error(
                    "[ContentManager] 채널 처리 오류 (건너뜀): %s — %s",
                    channel_id, e, exc_info=True
                )
        return all_candidates
