"""
ai/style_learner.py
===================
사용자의 과거 YouTube 댓글을 분석하여 글쓰기 스타일을 학습한다.

동작 흐름:
  1. YouTube API로 내 채널의 최근 댓글 수집 → style_samples 테이블 캐시
  2. Gemini Pro에 댓글 샘플 전송 → JSON 스타일 프로필 수신
  3. 스타일 프로필을 settings 테이블에 저장 (이후 comment_generator가 읽음)
  4. 마지막 학습 시각을 기록, 일정 주기(7일) 이상 지나면 재학습
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import google.generativeai as genai
from googleapiclient.errors import HttpError

from ai.prompts import STYLE_ANALYSIS_PROMPT
from db.database import DatabaseManager
from utils.logger import get_logger

log = get_logger("youtube_agent")

# 스타일 프로필 재학습 주기 (일)
_RESTYLE_INTERVAL_DAYS = 7
# 스타일 학습에 사용할 최대 댓글 수
_MAX_SAMPLE_COMMENTS = 30
# settings 테이블 키
_STYLE_PROFILE_KEY = "style_profile_json"
_STYLE_LAST_FETCHED_KEY = "style_last_fetched"


class StyleLearner:
    """
    사용자의 YouTube 댓글 스타일을 학습하고 관리한다.

    Args:
        youtube_service:  googleapiclient YouTube 서비스 객체
        gemini_model:     google.generativeai GenerativeModel 인스턴스
        db:               DatabaseManager 인스턴스
        my_channel_id:    내 YouTube 채널 ID (스타일 학습 대상)
    """

    def __init__(
        self,
        youtube_service,
        gemini_model: "genai.GenerativeModel",
        db: DatabaseManager,
        my_channel_id: str,
    ):
        self._yt = youtube_service
        self._model = gemini_model
        self._db = db
        self._my_channel_id = my_channel_id

    # ──────────────────────────────────────────────
    # 공개 인터페이스
    # ──────────────────────────────────────────────

    def get_style_profile(self, force_refresh: bool = False) -> dict:
        """
        스타일 프로필을 반환한다. 캐시가 유효하면 DB에서, 아니면 재학습한다.

        Args:
            force_refresh: True면 캐시 무시하고 무조건 재학습

        Returns:
            스타일 프로필 딕셔너리
        """
        if not force_refresh and self._is_cache_valid():
            profile = self._load_profile_from_db()
            if profile:
                log.info("[StyleLearner] 캐시된 스타일 프로필 사용.")
                return profile

        log.info("[StyleLearner] 스타일 프로필 재학습 시작...")
        profile = self._learn_style()
        self._save_profile_to_db(profile)
        return profile

    # ──────────────────────────────────────────────
    # 내부 메서드
    # ──────────────────────────────────────────────

    def _is_cache_valid(self) -> bool:
        """마지막 학습 시각이 _RESTYLE_INTERVAL_DAYS 이내인지 확인."""
        last_fetched = self._db.get_setting(_STYLE_LAST_FETCHED_KEY, "")
        if not last_fetched:
            return False
        try:
            last_dt = datetime.fromisoformat(last_fetched.replace("Z", "+00:00"))
            return datetime.now(tz=timezone.utc) - last_dt < timedelta(days=_RESTYLE_INTERVAL_DAYS)
        except ValueError:
            return False

    def _load_profile_from_db(self) -> Optional[dict]:
        """DB에서 스타일 프로필 JSON을 로드한다."""
        raw = self._db.get_setting(_STYLE_PROFILE_KEY, "")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _save_profile_to_db(self, profile: dict) -> None:
        """스타일 프로필을 DB에 저장하고 마지막 학습 시각을 갱신한다."""
        self._db.set_setting(_STYLE_PROFILE_KEY, json.dumps(profile, ensure_ascii=False))
        self._db.set_setting(
            _STYLE_LAST_FETCHED_KEY,
            datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        log.info("[StyleLearner] 스타일 프로필 DB 저장 완료.")

    def _learn_style(self) -> dict:
        """댓글 샘플 수집 → Gemini 분석 → 프로필 반환."""
        samples = self._fetch_my_comments()
        if not samples:
            log.warning("[StyleLearner] 수집된 댓글이 없습니다. 기본 프로필 사용.")
            return _default_style_profile()

        self._cache_samples_to_db(samples)
        profile = self._analyze_with_gemini(samples)
        return profile

    def _fetch_my_comments(self) -> list[str]:
        """
        내 채널에서 작성한 댓글을 YouTube API로 수집한다.
        commentThreads API의 authorChannelId 필터를 사용.
        """
        comments: list[str] = []
        try:
            # 내가 작성한 댓글: 특정 채널에서 내 채널 ID로 필터
            # YouTube API는 직접적인 'my comments' 엔드포인트가 없으므로
            # DB 캐시에서 먼저 로드 시도
            with self._db.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT comment_text FROM style_samples
                    ORDER BY like_count DESC, published_at DESC
                    LIMIT ?
                    """,
                    (_MAX_SAMPLE_COMMENTS,),
                ).fetchall()
            if rows:
                log.info("[StyleLearner] DB 캐시에서 %d개 댓글 샘플 로드.", len(rows))
                return [row["comment_text"] for row in rows]

            # DB 캐시가 없으면 API로 수집
            # 내 채널의 활동 목록 (댓글)
            log.info("[StyleLearner] YouTube API로 내 댓글 수집 중...")
            response = (
                self._yt.commentThreads()
                .list(
                    part="snippet",
                    allThreadsRelatedToChannelId=self._my_channel_id,
                    maxResults=_MAX_SAMPLE_COMMENTS,
                    order="time",
                )
                .execute()
            )
            for item in response.get("items", []):
                top_comment = item.get("snippet", {}).get("topLevelComment", {})
                snippet = top_comment.get("snippet", {})
                author_id = snippet.get("authorChannelId", {}).get("value", "")
                if author_id == self._my_channel_id:
                    text = snippet.get("textOriginal", "").strip()
                    if text:
                        comments.append(text)

        except HttpError as e:
            log.error("[StyleLearner] YouTube API 오류: %s", e)
        except Exception as e:
            log.error("[StyleLearner] 댓글 수집 오류: %s", e, exc_info=True)

        log.info("[StyleLearner] API에서 %d개 댓글 수집.", len(comments))
        return comments

    def _cache_samples_to_db(self, comment_texts: list[str]) -> None:
        """수집된 댓글 텍스트를 style_samples 테이블에 임시 캐시한다."""
        from datetime import datetime
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.get_connection() as conn:
            for i, text in enumerate(comment_texts):
                fake_id = f"manual_{i:04d}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO style_samples
                        (comment_id, video_id, comment_text, published_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (fake_id, "unknown", text, now),
                )

    def _analyze_with_gemini(self, comments: list[str]) -> dict:
        """Gemini Pro에 댓글 샘플을 전송하고 스타일 프로필을 수신한다."""
        # 댓글 샘플 포맷팅 (번호 + 따옴표)
        sample_text = "\n".join(
            f'{i+1}. "{c}"' for i, c in enumerate(comments[:_MAX_SAMPLE_COMMENTS])
        )
        prompt = STYLE_ANALYSIS_PROMPT.format(comment_samples=sample_text)

        try:
            log.info("[StyleLearner] Gemini Pro 스타일 분석 요청 중...")
            response = self._model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,       # 낮은 온도 = 일관된 분석
                    max_output_tokens=512,
                ),
            )
            raw_text = response.text.strip()
            profile = _extract_json(raw_text)
            log.info("[StyleLearner] 스타일 분석 완료: %s", profile.get("style_summary", ""))
            return profile
        except Exception as e:
            log.error("[StyleLearner] Gemini 분석 오류: %s", e, exc_info=True)
            return _default_style_profile()


def _extract_json(text: str) -> dict:
    """
    Gemini 응답에서 JSON 블록을 추출한다.
    ```json ... ``` 마크다운 코드블록 또는 순수 JSON 모두 처리.
    """
    # 코드 펜스 제거
    if "```json" in text:
        text = text.split("```json")[-1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        log.warning("[StyleLearner] JSON 파싱 실패 (%s). 기본 프로필 사용.", e)
        return _default_style_profile()


def _default_style_profile() -> dict:
    """학습 실패 시 사용되는 기본 스타일 프로필."""
    return {
        "tone": "친근하고 따뜻함",
        "sentence_length": "short",
        "emoji_usage": {"frequency": "moderate", "common_emojis": ["😊", "👍", "🙏"]},
        "honorifics": "informal",
        "typical_patterns": ["정말 좋았어요", "응원합니다", "감사해요"],
        "enthusiasm_level": "medium",
        "style_summary": "친근하고 짧은 문장으로 긍정적인 반응을 표현하는 스타일",
    }
