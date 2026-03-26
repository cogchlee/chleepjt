"""
ai/prompts.py
=============
Gemini Pro 프롬프트 템플릿 모음.

설계 원칙:
- 스타일 학습용 / 댓글 생성용 프롬프트를 명확히 분리
- f-string 대신 .format() 패턴 → 재사용 및 테스트 용이
- 외국어 목록과 언어 지시사항을 상수로 관리하여 외부에서 주입 가능
"""

from __future__ import annotations

# ──────────────────────────────────────────────
# 지원 외국어 매핑 (코드 → 언어명)
# ──────────────────────────────────────────────
SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "ja": "Japanese (日本語)",
    "zh": "Chinese Simplified (中文简体)",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "pt": "Portuguese (Português)",
    "id": "Indonesian (Bahasa Indonesia)",
    "th": "Thai (ภาษาไทย)",
    "vi": "Vietnamese (Tiếng Việt)",
}


# ──────────────────────────────────────────────
# 1. 스타일 분석 프롬프트
# ──────────────────────────────────────────────

STYLE_ANALYSIS_PROMPT = """
당신은 텍스트 스타일 분석 전문가입니다.

아래는 특정 유저가 YouTube에 작성한 실제 댓글 샘플입니다.
이 댓글들을 분석하여, 이 유저의 **글쓰기 스타일을 JSON으로 정리**해 주세요.

## 댓글 샘플:
{comment_samples}

## 분석 항목:
1. tone: 전반적인 어조 (예: "친근하고 유머러스함", "진지하고 감동적임" 등)
2. sentence_length: 문장 길이 경향 (short/medium/long)
3. emoji_usage: 이모지 사용 빈도 (none/rare/moderate/frequent) 및 자주 쓰는 이모지 목록
4. honorifics: 경어 사용 여부 (formal/informal/mixed)
5. typical_patterns: 자주 반복되는 표현 패턴이나 말버릇 (리스트)
6. enthusiasm_level: 열정/감탄의 정도 (low/medium/high)
7. style_summary: 위 분석을 바탕으로 이 유저의 스타일을 한 문장으로 요약

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

```json
{{
  "tone": "...",
  "sentence_length": "...",
  "emoji_usage": {{
    "frequency": "...",
    "common_emojis": ["...", "..."]
  }},
  "honorifics": "...",
  "typical_patterns": ["...", "..."],
  "enthusiasm_level": "...",
  "style_summary": "..."
}}
```
""".strip()


# ──────────────────────────────────────────────
# 2. 댓글 생성 프롬프트 (핵심)
# ──────────────────────────────────────────────

COMMENT_GENERATION_PROMPT = """
당신은 YouTube 댓글 작성 전문가입니다.
아래 정보를 바탕으로 자연스럽고 진정성 있는 댓글을 작성해 주세요.

## [1] 콘텐츠 정보
- 제목: {content_title}
- 유형: {content_type}
- 설명 (요약): {content_description}

## [2] 작성자 고유 스타일 프로필
{style_profile}

## [3] 댓글 작성 규칙
1. **한국어 + {foreign_lang_name}** 병기 형식으로 작성한다.
2. 형식: [한국어 댓글] + 줄바꿈 + [{foreign_lang_name} 번역]
3. 한국어 댓글은 [2]의 스타일 프로필을 **철저히 반영**한다.
4. 외국어 번역은 한국어 댓글의 뉘앙스를 그대로 살려 자연스럽게 번역한다.
5. 전체 글자 수: 한국어 기준 **30~80자** 이내 (너무 길면 스팸으로 인식됨).
6. 콘텐츠와 **직접적으로 관련된 내용**을 언급하여 진정성을 높인다.
7. 홍보성 문구, URL, 타 채널 언급은 **절대 포함하지 않는다**.
8. 이모지는 스타일 프로필의 빈도에 맞게 사용한다.

## [4] 출력 형식
반드시 아래 JSON 형식으로만 응답하세요.

```json
{{
  "comment_ko": "한국어 댓글만 (외국어 없이)",
  "comment_foreign": "{foreign_lang_code}: 외국어 번역만",
  "comment_full": "한국어 댓글\\n\\n외국어 번역 (최종 게시용 전체 댓글)",
  "reasoning": "이 댓글을 선택한 이유 (내부 참고용, 1-2문장)"
}}
```
""".strip()


# ──────────────────────────────────────────────
# 3. 댓글 재작성(수정) 프롬프트
# ──────────────────────────────────────────────

COMMENT_REVISION_PROMPT = """
아래 댓글을 사용자의 피드백에 맞게 수정해 주세요.

## 원본 댓글:
{original_comment}

## 사용자 피드백 / 수정 요청:
{user_feedback}

## 원래 콘텐츠 정보:
- 제목: {content_title}
- 스타일 프로필: {style_profile}

## 출력 형식
```json
{{
  "comment_ko": "수정된 한국어 댓글",
  "comment_foreign": "{foreign_lang_code}: 수정된 외국어 번역",
  "comment_full": "수정된 전체 댓글 (최종 게시용)",
  "changes_made": "변경 사항 요약 (1-2문장)"
}}
```
""".strip()


# ──────────────────────────────────────────────
# 4. 채널 언어 감지 프롬프트
# ──────────────────────────────────────────────

CHANNEL_LANGUAGE_DETECT_PROMPT = """
아래 YouTube 채널 정보를 보고, 이 채널의 주요 시청자층 언어를 추론하세요.

채널명: {channel_name}
채널 설명: {channel_description}
최근 영상 제목들:
{recent_titles}

지원 언어 코드: {supported_codes}

반드시 아래 JSON 형식으로만 응답하세요.
```json
{{
  "primary_language_code": "en",
  "confidence": "high/medium/low",
  "reasoning": "판단 근거 (1문장)"
}}
```
""".strip()
