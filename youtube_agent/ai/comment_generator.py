"""
ai/comment_generator.py
========================
Gemini Pro를 사용하여 [한글+외국어] 병기 댓글을 생성한다.

동작 흐름:
  1. StyleLearner에서 사용자 스타일 프로필 획득
  2. (선택) 채널 언어 자동 감지 또는 직접 지정
  3. COMMENT_GENERATION_PROMPT로 Gemini Pro 호출
  4. JSON 응답 파싱 → CommentResult 반환
  5. 실패 시 최대 2회 재시도

Telegram Phase 4에서 CommentResult를 받아 승인/거절/수정 처리한다.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import google.generativeai as genai

from ai.prompts import (
    COMMENT_GENERATION_PROMPT,
    COMMENT_REVISION_PROMPT,
    CHANNEL_LANGUAGE_DETECT_PROMPT,
    SUPPORTED_LANGUAGES,
)
from ai.style_learner import StyleLearner, _extract_json
from youtube.models import ContentItem
from db.database import DatabaseManager
from utils.logger import get_logger

log = get_logger("youtube_agent")

_MAX_RETRY = 2
_RETRY_DELAY = 3  # seconds
_DEFAULT_LANG = "en"


# ──────────────────────────────────────────────
# 결과 데이터 구조
# ──────────────────────────────────────────────

@dataclass
class CommentResult:
    """
    Gemini가 생성한 댓글 결과물.
    Telegram 봇(Phase 4)에서 직접 사용된다.
    """
    comment_ko: str               # 한국어 댓글 (단독)
    comment_foreign: str          # 외국어 번역 (단독)
    comment_full: str             # 최종 게시용 전체 댓글 (한+외 병기)
    foreign_lang_code: str        # 외국어 코드 (ex: 'en')
    foreign_lang_name: str        # 외국어 이름 (ex: 'English')
    content_item: ContentItem     # 원본 콘텐츠 참조
    reasoning: str = ""           # 생성 근거 (내부용)
    db_comment_id: Optional[int] = None  # DB에 저장된 comments_log.id
    is_revised: bool = False      # 텔레그램에서 수정됐는지 여부

    @property
    def preview(self) -> str:
        """텔레그램 메시지용 미리보기 텍스트."""
        lang_name = self.foreign_lang_name
        return (
            f"📝 *댓글 생성 완료*\n\n"
            f"🎬 콘텐츠: {self.content_item.title[:40]}\n"
            f"🌐 언어: 한국어 + {lang_name}\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"{self.comment_full}\n"
            f"━━━━━━━━━━━━━━━━━\n\n"
            f"💡 _{self.reasoning}_"
        )


# ──────────────────────────────────────────────
# 메인 클래스
# ──────────────────────────────────────────────

class CommentGenerator:
    """
    Gemini Pro 기반 [한글+외국어] 병기 댓글 생성기.

    Args:
        gemini_model:    google.generativeai GenerativeModel 인스턴스
        style_learner:   StyleLearner 인스턴스
        db:              DatabaseManager 인스턴스
        default_lang:    기본 외국어 코드 (SUPPORTED_LANGUAGES 참고)
        temperature:     Gemini 생성 온도 (0.0~1.0, 기본 0.75)
    """

    def __init__(
        self,
        gemini_model: "genai.GenerativeModel",
        style_learner: StyleLearner,
        db: DatabaseManager,
        default_lang: str = _DEFAULT_LANG,
        temperature: float = 0.75,
    ):
        self._model = gemini_model
        self._style_learner = style_learner
        self._db = db
        self.default_lang = default_lang
        self.temperature = temperature
        self._style_cache: Optional[dict] = None

    # ──────────────────────────────────────────────
    # 공개 인터페이스
    # ──────────────────────────────────────────────

    def generate(
        self,
        content: ContentItem,
        lang_code: Optional[str] = None,
        save_to_db: bool = True,
    ) -> Optional[CommentResult]:
        """
        단일 콘텐츠에 대한 [한글+외국어] 병기 댓글을 생성한다.

        Args:
            content:     댓글을 달 ContentItem
            lang_code:   외국어 코드 (None 시 config 기본값 사용)
            save_to_db:  True면 comments_log 테이블에 저장

        Returns:
            CommentResult 또는 생성 실패 시 None
        """
        lang_code = lang_code or self.default_lang
        if lang_code not in SUPPORTED_LANGUAGES:
            log.warning("[CommentGenerator] 미지원 언어 '%s'. 기본값 '%s' 사용.", lang_code, _DEFAULT_LANG)
            lang_code = _DEFAULT_LANG
        lang_name = SUPPORTED_LANGUAGES[lang_code]

        # 스타일 프로필 (캐시)
        if self._style_cache is None:
            self._style_cache = self._style_learner.get_style_profile()

        style_str = _format_style_profile(self._style_cache)
        prompt = COMMENT_GENERATION_PROMPT.format(
            content_title=content.title,
            content_type=_content_type_label(content.content_type),
            content_description=content.description[:300] if content.description else "정보 없음",
            style_profile=style_str,
            foreign_lang_name=lang_name,
            foreign_lang_code=lang_code,
        )

        result_dict = self._call_gemini_with_retry(prompt, context="generate")
        if not result_dict:
            return None

        result = CommentResult(
            comment_ko=result_dict.get("comment_ko", ""),
            comment_foreign=result_dict.get("comment_foreign", ""),
            comment_full=result_dict.get("comment_full", ""),
            foreign_lang_code=lang_code,
            foreign_lang_name=lang_name,
            content_item=content,
            reasoning=result_dict.get("reasoning", ""),
        )

        if not result.comment_full:
            log.warning("[CommentGenerator] 빈 댓글 생성됨. 건너뜀.")
            return None

        if save_to_db:
            db_id = self._db.add_comment_log(
                content_id=content.content_id,
                content_type=content.content_type,
                channel_id=content.channel_id,
                comment_ko=result.comment_ko,
                comment_full=result.comment_full,
            )
            result.db_comment_id = db_id
            log.info(
                "[CommentGenerator] 댓글 DB 저장 완료. id=%d | %s",
                db_id,
                result.comment_ko[:30],
            )

        return result

    def revise(
        self,
        original: CommentResult,
        user_feedback: str,
    ) -> Optional[CommentResult]:
        """
        텔레그램에서 사용자 피드백을 받아 댓글을 수정한다 (Phase 4 연동).

        Args:
            original:      원본 CommentResult
            user_feedback: 텔레그램에서 받은 수정 요청 텍스트

        Returns:
            수정된 CommentResult 또는 실패 시 None
        """
        style_str = _format_style_profile(self._style_cache or {})
        prompt = COMMENT_REVISION_PROMPT.format(
            original_comment=original.comment_full,
            user_feedback=user_feedback,
            content_title=original.content_item.title,
            style_profile=style_str,
            foreign_lang_code=original.foreign_lang_code,
        )

        result_dict = self._call_gemini_with_retry(prompt, context="revise")
        if not result_dict:
            return None

        revised = CommentResult(
            comment_ko=result_dict.get("comment_ko", original.comment_ko),
            comment_foreign=result_dict.get("comment_foreign", original.comment_foreign),
            comment_full=result_dict.get("comment_full", original.comment_full),
            foreign_lang_code=original.foreign_lang_code,
            foreign_lang_name=original.foreign_lang_name,
            content_item=original.content_item,
            reasoning=result_dict.get("changes_made", ""),
            db_comment_id=original.db_comment_id,
            is_revised=True,
        )
        log.info("[CommentGenerator] 댓글 수정 완료: %s", revised.comment_ko[:30])
        return revised

    def detect_channel_language(
        self,
        channel_name: str,
        channel_description: str,
        recent_titles: list[str],
    ) -> str:
        """
        채널 정보를 분석하여 주요 시청자 언어를 추론한다.

        Returns:
            언어 코드 (ex: 'en', 'ja'). 실패 시 기본값 반환.
        """
        titles_text = "\n".join(f"- {t}" for t in recent_titles[:10])
        supported_codes = ", ".join(SUPPORTED_LANGUAGES.keys())
        prompt = CHANNEL_LANGUAGE_DETECT_PROMPT.format(
            channel_name=channel_name,
            channel_description=channel_description[:200],
            recent_titles=titles_text,
            supported_codes=supported_codes,
        )

        result = self._call_gemini_with_retry(prompt, context="lang_detect")
        if result:
            code = result.get("primary_language_code", self.default_lang)
            if code in SUPPORTED_LANGUAGES:
                log.info(
                    "[CommentGenerator] 채널 언어 감지: %s (%s)",
                    code,
                    result.get("confidence", "?"),
                )
                return code

        return self.default_lang

    # ──────────────────────────────────────────────
    # 내부 Gemini 호출
    # ──────────────────────────────────────────────

    def _call_gemini_with_retry(
        self, prompt: str, context: str = ""
    ) -> Optional[dict]:
        """Gemini Pro를 호출하고 JSON을 파싱한다. 최대 _MAX_RETRY회 재시도."""
        for attempt in range(1, _MAX_RETRY + 2):
            try:
                response = self._model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=self.temperature,
                        max_output_tokens=800,
                    ),
                )
                raw_text = response.text.strip()
                parsed = _extract_json(raw_text)
                if parsed:
                    return parsed
                log.warning(
                    "[CommentGenerator][%s] JSON 파싱 실패 (시도 %d/%d).",
                    context, attempt, _MAX_RETRY + 1,
                )
            except Exception as e:
                log.error(
                    "[CommentGenerator][%s] Gemini 호출 오류 (시도 %d/%d): %s",
                    context, attempt, _MAX_RETRY + 1, e,
                )
            if attempt <= _MAX_RETRY:
                time.sleep(_RETRY_DELAY * attempt)

        log.error("[CommentGenerator][%s] 최대 재시도 초과. None 반환.", context)
        return None


# ──────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────

def _format_style_profile(profile: dict) -> str:
    """스타일 프로필 딕셔너리를 프롬프트용 텍스트로 변환한다."""
    if not profile:
        return "기본 스타일: 친근하고 짧은 문장, 이모지 적당히 사용"
    lines = []
    lines.append(f"- 어조: {profile.get('tone', '친근함')}")
    lines.append(f"- 문장 길이: {profile.get('sentence_length', 'short')}")
    emoji_info = profile.get("emoji_usage", {})
    lines.append(
        f"- 이모지: {emoji_info.get('frequency', 'moderate')} "
        f"(자주 쓰는 이모지: {', '.join(emoji_info.get('common_emojis', ['😊']))})"
    )
    lines.append(f"- 경어: {profile.get('honorifics', 'informal')}")
    patterns = profile.get("typical_patterns", [])
    if patterns:
        lines.append(f"- 말버릇: {' / '.join(patterns[:3])}")
    lines.append(f"- 열정도: {profile.get('enthusiasm_level', 'medium')}")
    lines.append(f"- 요약: {profile.get('style_summary', '')}")
    return "\n".join(lines)


def _content_type_label(content_type: str) -> str:
    return {
        "video": "일반 YouTube 동영상",
        "short": "YouTube Shorts (세로형 짧은 영상)",
        "community": "YouTube 커뮤니티 게시글",
    }.get(content_type, content_type)
