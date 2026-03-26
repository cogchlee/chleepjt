"""
youtube/filter.py
=================
수집된 콘텐츠를 SQLite DB와 대조하여 '작성 후보군'만 반환하는 필터 모듈.

필터링 기준:
1. processed_contents 테이블 → 이미 처리된 콘텐츠 제외
2. comments_log 테이블 → 'pending'/'approved'/'posted' 상태 댓글이 있는 콘텐츠 제외
3. 최소 게시 경과 시간 기준 (너무 신선한 게시물 제외, 봇 감지 회피)
4. 중복 content_id 제거
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from youtube.models import ContentItem
from db.database import DatabaseManager


# 게시 후 최소 경과 시간 (너무 즉각적인 댓글은 봇처럼 보임)
_MIN_AGE_MINUTES = 30


class ContentFilter:
    """
    ContentItem 리스트를 DB 상태와 대조하여 댓글 작성 후보만 반환한다.

    Args:
        db:             DatabaseManager 인스턴스
        min_age_min:    업로드 후 최소 경과 시간(분). ISO 8601 날짜 파싱 가능한 경우만 적용.
    """

    def __init__(
        self,
        db: DatabaseManager,
        min_age_min: int = _MIN_AGE_MINUTES,
    ):
        self.db = db
        self.min_age_min = min_age_min

    # ──────────────────────────────────────────────
    # 공개 인터페이스
    # ──────────────────────────────────────────────

    def filter_candidates(
        self,
        items: list[ContentItem],
        exclude_statuses: tuple[str, ...] = ("pending", "approved", "posted"),
    ) -> list[ContentItem]:
        """
        댓글 작성 후보군을 반환한다.

        필터 체인:
          1. 중복 content_id 제거
          2. processed_contents 테이블 대조 (처리 완료된 콘텐츠 제외)
          3. comments_log 테이블 대조 (진행 중/완료된 댓글이 있는 콘텐츠 제외)
          4. 최소 게시 경과 시간 필터

        Args:
            items:           수집된 ContentItem 리스트 (video / short / community 혼합)
            exclude_statuses: 이 상태의 댓글이 존재하는 콘텐츠는 후보에서 제외

        Returns:
            작성 후보 ContentItem 리스트 (published_at 내림차순 정렬)
        """
        if not items:
            return []

        # 1. 중복 제거 (content_id 기준, 첫 번째 항목 우선)
        seen: set[str] = set()
        deduped: list[ContentItem] = []
        for item in items:
            if item.content_id not in seen:
                seen.add(item.content_id)
                deduped.append(item)

        # 2 & 3. DB 대조 필터
        not_processed = self._filter_by_processed_table(deduped)
        not_commented = self._filter_by_comments_log(not_processed, exclude_statuses)

        # 4. 최소 경과 시간 필터
        candidates = self._filter_by_age(not_commented)

        return candidates

    def get_filter_stats(self, original: list[ContentItem], candidates: list[ContentItem]) -> dict:
        """필터링 통계를 반환한다."""
        return {
            "original_count": len(original),
            "candidate_count": len(candidates),
            "filtered_out":    len(original) - len(candidates),
            "types": {
                "video":     sum(1 for c in candidates if c.content_type == "video"),
                "short":     sum(1 for c in candidates if c.content_type == "short"),
                "community": sum(1 for c in candidates if c.content_type == "community"),
            },
        }

    # ──────────────────────────────────────────────
    # 내부 필터 메서드
    # ──────────────────────────────────────────────

    def _filter_by_processed_table(
        self, items: list[ContentItem]
    ) -> list[ContentItem]:
        """processed_contents에 없는 항목만 반환한다."""
        result = []
        for item in items:
            if not self.db.is_content_processed(item.content_id, item.channel_id):
                result.append(item)
        return result

    def _filter_by_comments_log(
        self,
        items: list[ContentItem],
        exclude_statuses: tuple[str, ...],
    ) -> list[ContentItem]:
        """comments_log에서 특정 상태 댓글이 없는 항목만 반환한다."""
        if not items or not exclude_statuses:
            return items

        # 한 번의 쿼리로 모든 content_id 조회 (N+1 방지)
        content_ids = [item.content_id for item in items]
        placeholders = ",".join("?" * len(content_ids))
        status_placeholders = ",".join("?" * len(exclude_statuses))

        with self.db.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT DISTINCT content_id FROM comments_log
                WHERE content_id IN ({placeholders})
                  AND status IN ({status_placeholders})
                """,
                (*content_ids, *exclude_statuses),
            ).fetchall()

        excluded_ids = {row["content_id"] for row in rows}
        return [item for item in items if item.content_id not in excluded_ids]

    def _filter_by_age(
        self, items: list[ContentItem]
    ) -> list[ContentItem]:
        """
        ISO 8601 날짜 파싱이 가능한 경우, 최소 경과 시간보다 오래된 항목만 반환.
        커뮤니티 게시글은 상대 시각(예: "3일 전")이므로 필터 생략.
        """
        if self.min_age_min <= 0:
            return items

        now = datetime.now(tz=timezone.utc)
        threshold = now - timedelta(minutes=self.min_age_min)
        result = []

        for item in items:
            if item.content_type == "community":
                # 상대 시각 파싱 불가 → 통과
                result.append(item)
                continue
            pub = _parse_iso_datetime(item.published_at)
            if pub is None or pub <= threshold:
                result.append(item)
            # else: 너무 최근 게시물 → 제외

        return result


def _parse_iso_datetime(iso_str: str) -> Optional[datetime]:
    """ISO 8601 문자열을 timezone-aware datetime으로 파싱한다."""
    if not iso_str:
        return None
    try:
        # Python 3.11+: datetime.fromisoformat 완전 지원
        # 3.10 이하: 'Z' suffix를 '+00:00'으로 교체
        normalized = iso_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, AttributeError):
        return None
