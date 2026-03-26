"""
youtube/models.py
=================
콘텐츠 아이템 공통 데이터 구조.
모든 수집 모듈이 이 타입을 반환한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

ContentType = Literal["video", "short", "community"]


@dataclass
class ContentItem:
    """
    단일 YouTube 콘텐츠를 표현하는 데이터 클래스.

    Attributes:
        content_id:   YouTube의 고유 ID (video_id 또는 post_id)
        content_type: 'video' | 'short' | 'community'
        channel_id:   업로드 채널 ID
        title:        영상 제목 또는 게시글 미리보기 텍스트
        url:          직접 접근 URL
        published_at: 게시 시각 (ISO 8601, UTC)
        description:  영상 설명 / 게시글 본문 (요약, 선택)
        thumbnail_url: 썸네일 URL (선택)
        duration_sec: 영상 길이 초 단위 (쇼츠 판별용, 선택)
        view_count:   조회 수 (선택)
    """

    content_id: str
    content_type: ContentType
    channel_id: str
    title: str
    url: str
    published_at: str                   # ISO 8601 UTC string
    description: str = ""
    thumbnail_url: str = ""
    duration_sec: int | None = None     # None = 알 수 없음
    view_count: int = 0

    # ── 수집 메타데이터 (내부 사용) ──
    fetched_at: str = field(
        default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def to_dict(self) -> dict:
        return {
            "content_id":     self.content_id,
            "content_type":   self.content_type,
            "channel_id":     self.channel_id,
            "title":          self.title,
            "url":            self.url,
            "published_at":   self.published_at,
            "description":    self.description,
            "thumbnail_url":  self.thumbnail_url,
            "duration_sec":   self.duration_sec,
            "view_count":     self.view_count,
            "fetched_at":     self.fetched_at,
        }

    def __repr__(self) -> str:
        return (
            f"<ContentItem [{self.content_type.upper()}] "
            f"id={self.content_id} title={self.title[:30]!r}>"
        )
