"""
test_phase3.py
==============
Phase 3 Gemini Pro 연동 테스트 스크립트.

모드 1 (--mock):  실제 API 없이 프롬프트 구성 및 JSON 파싱만 테스트
모드 2 (기본):    실제 Gemini API + YouTube API 사용하여 전체 흐름 테스트

사용법:
    # API 키 없이 구조 테스트
    python test_phase3.py --mock

    # 실제 API 사용 (1개 채널, 영어 병기)
    python test_phase3.py --channel UCxxxxxx --lang en

    # 일본어 병기
    python test_phase3.py --channel UCxxxxxx --lang ja
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Windows PowerShell cp949 환경에서 이모지/한글 출력 보장
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run_mock_test():
    """실제 API 없이 프롬프트 구성 및 파싱 로직만 테스트한다."""
    print("=" * 55)
    print("  Phase 3 Mock Test (API 호출 없음)")
    print("=" * 55)

    from ai.prompts import (
        STYLE_ANALYSIS_PROMPT,
        COMMENT_GENERATION_PROMPT,
        SUPPORTED_LANGUAGES,
    )
    from ai.style_learner import _extract_json, _default_style_profile
    from ai.comment_generator import _format_style_profile, _content_type_label
    from youtube.models import ContentItem
    from datetime import datetime, timezone

    # 1. 스타일 프로필 기본값 확인
    profile = _default_style_profile()
    print("\n[1] 기본 스타일 프로필:")
    for k, v in profile.items():
        # 이모지 포함 값은 ASCII escape로 출력 (Windows cp949 대응)
        safe_v = str(v).encode("ascii", errors="replace").decode("ascii")
        print(f"    {k}: {safe_v}")

    # 2. 스타일 프로필 → 텍스트 포맷 확인
    style_text = _format_style_profile(profile)
    print(f"\n[2] 스타일 프로필 텍스트 포맷:")
    print(style_text)

    # 3. 댓글 생성 프롬프트 구성 확인
    test_content = ContentItem(
        content_id="dQw4w9WgXcQ",
        content_type="video",
        channel_id="UC_TEST",
        title="Never Gonna Give You Up",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        published_at=datetime.now(tz=timezone.utc).isoformat(),
        description="Official music video by Rick Astley.",
    )
    prompt = COMMENT_GENERATION_PROMPT.format(
        content_title=test_content.title,
        content_type=_content_type_label(test_content.content_type),
        content_description=test_content.description,
        style_profile=style_text,
        foreign_lang_name="English",
        foreign_lang_code="en",
    )
    print(f"\n[3] 댓글 생성 프롬프트 (일부):")
    print(prompt[:400] + "...")

    # 4. JSON 추출 파싱 테스트
    fake_gemini_response = """
    ```json
    {
      "comment_ko": "진짜 레전드 노래 ㅋㅋㅋ 이 세상 끝날 때까지 들을 것 같아요 😂",
      "comment_foreign": "en: This is a legendary song lol, feels like I'll listen to this until the end of the world 😂",
      "comment_full": "진짜 레전드 노래 ㅋㅋㅋ 이 세상 끝날 때까지 들을 것 같아요 😂\\n\\nen: This is a legendary song lol, feels like I'll listen to this until the end of the world 😂",
      "reasoning": "친근하고 유머러스한 스타일에 맞게 작성, 영상의 막강한 영향력을 유쾌하게 표현"
    }
    ```
    """
    parsed = _extract_json(fake_gemini_response)
    print("\n[4] JSON 파싱 테스트:")
    keys_found = list(parsed.keys())
    print(f"    파싱된 키: {keys_found}")
    assert "comment_ko" in parsed, "comment_ko key missing"
    assert "comment_full" in parsed, "comment_full key missing"
    assert "comment_foreign" in parsed, "comment_foreign key missing"
    print("    [OK] 모든 필수 키 존재 확인.")

    # 5. 지원 언어 목록
    print(f"\n[5] 지원 외국어: {len(SUPPORTED_LANGUAGES)}개")
    for code, name in SUPPORTED_LANGUAGES.items():
        safe_name = name.encode("ascii", errors="replace").decode("ascii")
        print(f"    {code}: {safe_name}")

    print("\n[OK] Mock 테스트 완료!")


def run_live_test(channel_id: str, lang_code: str):
    """실제 Gemini API와 YouTube API를 사용하는 전체 흐름 테스트."""
    import config
    from utils.logger import setup_logger, get_logger
    from db.database import get_db_manager
    from auth.oauth import YouTubeAuthManager
    from ai.style_learner import StyleLearner
    from ai.comment_generator import CommentGenerator
    from youtube.content_manager import ContentManager
    import google.generativeai as genai

    setup_logger("youtube_agent", log_dir=str(config.LOG_DIR))
    log = get_logger("youtube_agent")

    print("=" * 55)
    print("  Phase 3 Live Test")
    print("=" * 55)

    # ── 초기화 ──
    db = get_db_manager(config.DB_PATH)
    auth_mgr = YouTubeAuthManager(
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
        token_path=config.TOKEN_PATH,
        redirect_uri=config.GOOGLE_REDIRECT_URI,
    )
    yt = auth_mgr.get_youtube_client()

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)

    style_learner = StyleLearner(
        youtube_service=yt,
        gemini_model=model,
        db=db,
        my_channel_id=config.MY_CHANNEL_ID,
    )
    generator = CommentGenerator(
        gemini_model=model,
        style_learner=style_learner,
        db=db,
        default_lang=lang_code,
    )

    # ── 스타일 학습 ──
    print("\n[1] 스타일 프로필 로드 중...")
    profile = style_learner.get_style_profile()
    print(f"    스타일: {profile.get('style_summary', 'N/A')}")

    # ── 콘텐츠 수집 (최신 1개) ──
    print(f"\n[2] 채널 콘텐츠 수집 중: {channel_id}")
    content_mgr = ContentManager(
        youtube_service=yt, db=db,
        max_videos=5, include_community=False,
    )
    candidates = content_mgr.discover_candidates(channel_id)
    if not candidates:
        print("    후보 콘텐츠 없음. --channel 값을 확인하세요.")
        return

    # ── 댓글 생성 (첫 번째 후보만) ──
    target = candidates[0]
    print(f"\n[3] 댓글 생성 대상: [{target.content_type.upper()}] {target.title}")
    print(f"    URL: {target.url}")

    result = generator.generate(target, lang_code=lang_code, save_to_db=False)
    if not result:
        print("    댓글 생성 실패.")
        return

    print(f"\n[4] 생성된 댓글:")
    print("    " + "-" * 45)
    for line in result.comment_full.split("\n"):
        print(f"    {line}")
    print("    " + "-" * 45)
    print(f"    [근거] {result.reasoning}")
    print(f"\n[OK] Phase 3 Live 테스트 완료!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 Gemini 댓글 생성 테스트")
    parser.add_argument("--mock", action="store_true", help="API 없이 구조 테스트만 실행")
    parser.add_argument("--channel", type=str, help="대상 채널 ID")
    parser.add_argument("--lang", type=str, default="en", help="외국어 코드 (default: en)")
    args = parser.parse_args()

    if args.mock:
        run_mock_test()
    elif args.channel:
        run_live_test(args.channel, args.lang)
    else:
        print("사용법: python test_phase3.py --mock")
        print("        python test_phase3.py --channel UCxxxxxx --lang en")
        sys.exit(1)
