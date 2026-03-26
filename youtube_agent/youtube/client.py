"""
youtube/client.py
=================
YouTube Data API v3 래퍼.

설계 원칙:
- `search` API 대신 `playlistItems` API 사용 → 할당량 절약
  (search: 100 quota / call, playlistItems: 1 quota / call)
- ISO 8601 duration → 초 변환으로 쇼츠(≤60초) 자동 판별
- 채널의 'uploads' 플레이리스트 ID 캐싱 (재요청 방지)
"""

import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from googleapiclient.errors import HttpError

from youtube.models import ContentItem

# 쇼츠 기준: 60초 이하 세로형 영상
_SHORTS_MAX_SEC = 60

# ISO 8601 duration 파싱 정규식 (ex: PT1H2M3S, PT45S)
_DURATION_RE = re.compile(
    r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
)


def _parse_duration(iso_duration: str) -> int:
    """ISO 8601 duration 문자열을 초 단위 정수로 변환."""
    m = _DURATION_RE.match(iso_duration or "")
    if not m:
        return 0
    days, hours, minutes, seconds = (int(v or 0) for v in m.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _make_video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _make_shorts_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}"


class YouTubeAPIClient:
    """
    YouTube Data API v3 클라이언트 래퍼.

    Args:
        youtube_service: `googleapiclient.discovery.build()`로 생성한 서비스 객체.
        max_results:     채널당 최대 수집 영상 수 (기본 20, 최대 50).
    """

    def __init__(self, youtube_service, max_results: int = 20):
        self._yt = youtube_service
        self.max_results = min(max_results, 50)
        self._uploads_playlist_cache: dict[str, str] = {}  # channel_id → playlist_id

    # ──────────────────────────────────────────────
    # 공개 인터페이스
    # ──────────────────────────────────────────────

    def get_uploads_playlist_id(self, channel_id: str) -> Optional[str]:
        """
        채널의 'uploads' 플레이리스트 ID를 반환한다.
        결과는 메모리 캐시에 저장되어 재요청하지 않는다 (quota: 1).
        """
        if channel_id in self._uploads_playlist_cache:
            return self._uploads_playlist_cache[channel_id]

        try:
            resp = (
                self._yt.channels()
                .list(part="contentDetails", id=channel_id)
                .execute()
            )
            items = resp.get("items", [])
            if not items:
                return None
            playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
            self._uploads_playlist_cache[channel_id] = playlist_id
            return playlist_id
        except HttpError as e:
            print(f"[YouTubeAPIClient] get_uploads_playlist_id error: {e}")
            return None

    def fetch_recent_videos(
        self, channel_id: str, page_token: Optional[str] = None
    ) -> list[ContentItem]:
        """
        채널의 최신 동영상/쇼츠를 수집한다 (playlistItems API, quota: 1+N).
        쇼츠(≤60초)는 자동으로 'short' 타입으로 분류된다.

        Returns:
            ContentItem 리스트 (video + short 혼합)
        """
        playlist_id = self.get_uploads_playlist_id(channel_id)
        if not playlist_id:
            print(f"[YouTubeAPIClient] No uploads playlist for channel: {channel_id}")
            return []

        # Step 1: playlistItems로 video_id 목록 수집 (quota: 1)
        try:
            pl_resp = (
                self._yt.playlistItems()
                .list(
                    part="contentDetails,snippet",
                    playlistId=playlist_id,
                    maxResults=self.max_results,
                    pageToken=page_token,
                )
                .execute()
            )
        except HttpError as e:
            print(f"[YouTubeAPIClient] playlistItems error: {e}")
            return []

        playlist_items = pl_resp.get("items", [])
        if not playlist_items:
            return []

        video_ids = [
            item["contentDetails"]["videoId"]
            for item in playlist_items
            if item.get("contentDetails", {}).get("videoId")
        ]

        # Step 2: videos.list로 duration 일괄 조회 (quota: 1, 최대 50개)
        try:
            vid_resp = (
                self._yt.videos()
                .list(
                    part="contentDetails,statistics,snippet",
                    id=",".join(video_ids),
                )
                .execute()
            )
        except HttpError as e:
            print(f"[YouTubeAPIClient] videos.list error: {e}")
            return []

        # video_id → {duration, statistics} 맵
        details_map: dict[str, dict] = {
            item["id"]: item for item in vid_resp.get("items", [])
        }

        results: list[ContentItem] = []
        for pl_item in playlist_items:
            video_id = pl_item.get("contentDetails", {}).get("videoId", "")
            snippet = pl_item.get("snippet", {})
            detail = details_map.get(video_id, {})

            duration_str = detail.get("contentDetails", {}).get("duration", "")
            duration_sec = _parse_duration(duration_str)

            # 쇼츠 판별: 60초 이하
            if 0 < duration_sec <= _SHORTS_MAX_SEC:
                content_type = "short"
                url = _make_shorts_url(video_id)
            else:
                content_type = "video"
                url = _make_video_url(video_id)

            stats = detail.get("statistics", {})
            vid_snippet = detail.get("snippet", snippet)  # videos.list snippet 우선

            results.append(
                ContentItem(
                    content_id=video_id,
                    content_type=content_type,
                    channel_id=channel_id,
                    title=vid_snippet.get("title", snippet.get("title", "")),
                    url=url,
                    published_at=vid_snippet.get(
                        "publishedAt", snippet.get("publishedAt", "")
                    ),
                    description=vid_snippet.get("description", "")[:500],
                    thumbnail_url=(
                        vid_snippet.get("thumbnails", {})
                        .get("high", {})
                        .get("url", "")
                    ),
                    duration_sec=duration_sec if duration_sec > 0 else None,
                    view_count=int(stats.get("viewCount", 0)),
                )
            )

        return results
