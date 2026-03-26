"""
telegram_bot/poster.py
======================
YouTube 댓글 실제 게시 모듈.
Telegram Bot 핸들러(handlers.py)가 승인 신호를 받으면 이 모듈을 호출한다.

지원 유형:
  - video / short: YouTube Data API v3 comments.insert
  - community: (Phase 5에서 Playwright로 연결 예정)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from googleapiclient.errors import HttpError

from db.database import DatabaseManager
from utils.logger import get_logger

log = get_logger("youtube_agent")


class CommentPoster:
    """
    YouTube 댓글 게시를 담당한다.

    Args:
        youtube_service: 인증된 googleapiclient YouTube 서비스 객체
        db:              DatabaseManager 인스턴스
    """

    def __init__(self, youtube_service, db: DatabaseManager):
        self._yt = youtube_service
        self._db = db

    def post_comment(
        self,
        content_id: str,
        content_type: str,
        channel_id: str,
        comment_text: str,
        db_comment_id: int | None = None,
    ) -> tuple[bool, str]:
        """
        댓글을 YouTube에 게시한다.

        Args:
            content_id:    YouTube 영상/게시글 ID
            content_type:  'video' | 'short' | 'community'
            channel_id:    채널 ID (처리 완료 표시용)
            comment_text:  게시할 최종 댓글 텍스트
            db_comment_id: comments_log row ID (상태 업데이트용)

        Returns:
            (success: bool, message: str)
        """
        if content_type in ("video", "short"):
            return self._post_video_comment(
                content_id, channel_id, comment_text, db_comment_id
            )
        elif content_type == "community":
            # Phase 5: Playwright 자동화 연결 예정
            msg = (
                f"커뮤니티 게시글({content_id}) 댓글은 Phase 5(Playwright)에서 지원됩니다. "
                f"현재는 '게시됨'으로만 표시합니다."
            )
            log.warning("[CommentPoster] %s", msg)
            if db_comment_id:
                self._db.update_comment_status(db_comment_id, "posted")
                self._db.mark_content_processed(content_id, channel_id, content_type)
            return True, msg
        else:
            return False, f"알 수 없는 content_type: {content_type}"

    def _post_video_comment(
        self,
        video_id: str,
        channel_id: str,
        comment_text: str,
        db_comment_id: int | None,
    ) -> tuple[bool, str]:
        """YouTube Data API v3로 영상 댓글을 게시한다."""
        try:
            resp = (
                self._yt.commentThreads()
                .insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "videoId": video_id,
                            "topLevelComment": {
                                "snippet": {
                                    "textOriginal": comment_text
                                }
                            },
                        }
                    },
                )
                .execute()
            )
            posted_id = resp.get("id", "unknown")
            log.info(
                "[CommentPoster] 댓글 게시 성공. video_id=%s, comment_id=%s",
                video_id, posted_id,
            )
            if db_comment_id:
                self._db.update_comment_status(db_comment_id, "posted")
            self._db.mark_content_processed(video_id, channel_id, "video")

            # 전체 게시 횟수 카운터 증가
            total = int(self._db.get_setting("total_comments_posted", "0")) + 1
            self._db.set_setting("total_comments_posted", str(total))

            return True, f"댓글 게시 완료! (comment_id: {posted_id})"

        except HttpError as e:
            err_str = str(e)
            log.error(
                "[CommentPoster] HTTP 오류: %s | video_id=%s", err_str, video_id
            )
            if db_comment_id:
                self._db.update_comment_status(
                    db_comment_id, "failed", error_msg=err_str
                )
            if "commentsDisabled" in err_str:
                return False, "댓글이 비활성화된 영상입니다."
            if "forbidden" in err_str.lower() or "403" in err_str:
                return False, "권한 오류 (scopes 또는 채널 권한 확인 필요)."
            return False, f"YouTube API 오류: {e}"

        except Exception as e:
            log.error(
                "[CommentPoster] 예상치 못한 오류: %s | video_id=%s", e, video_id,
                exc_info=True,
            )
            if db_comment_id:
                self._db.update_comment_status(
                    db_comment_id, "failed", error_msg=str(e)
                )
            return False, f"예상치 못한 오류: {e}"
