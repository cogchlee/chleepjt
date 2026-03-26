"""
test_phase4.py
==============
Phase 4 Telegram 봇 임포트 및 구조 검증 스크립트.

모드 1 (--mock):  실제 API 없이 핸들러/메시지/키보드 구조만 검증
모드 2 (--live):  실제 봇 토큰으로 테스트 메시지 전송 및 폴링 시작

사용법:
    python test_phase4.py --mock
    python test_phase4.py --live   # .env 설정 필요
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run_mock_test():
    print("=" * 55)
    print("  Phase 4 Mock Test")
    print("=" * 55)

    from telegram_bot.handlers import (
        build_approval_keyboard,
        build_comment_message,
        _parse_callback,
        CB_APPROVE, CB_EDIT, CB_SKIP,
        WAITING_EDIT,
    )

    # 1. 콜백 데이터 파싱
    cb_approve = f"{CB_APPROVE}:42:dQw4w9WgXcQ"
    cb_edit    = f"{CB_EDIT}:42:dQw4w9WgXcQ"
    cb_skip    = f"{CB_SKIP}:42:dQw4w9WgXcQ"

    for cb in [cb_approve, cb_edit, cb_skip]:
        action, db_id, content_id = _parse_callback(cb)
        assert db_id == 42,              f"db_id mismatch: {db_id}"
        assert content_id == "dQw4w9WgXcQ", f"content_id mismatch: {content_id}"
        print(f"  [OK] _parse_callback('{cb[:20]}...'): action={action}, db_id={db_id}")

    # 2. 인라인 키보드 구성
    kb = build_approval_keyboard(db_comment_id=42, content_id="dQw4w9WgXcQ")
    assert kb is not None
    rows = kb.inline_keyboard
    assert len(rows) == 2,         f"Expected 2 rows, got {len(rows)}"
    assert len(rows[0]) == 1,      "Row 0 should have 1 button (Approve)"
    assert len(rows[1]) == 2,      "Row 1 should have 2 buttons (Edit, Skip)"
    approve_btn = rows[0][0]
    edit_btn    = rows[1][0]
    skip_btn    = rows[1][1]
    assert CB_APPROVE in approve_btn.callback_data, "Approve button data wrong"
    assert CB_EDIT    in edit_btn.callback_data,    "Edit button data wrong"
    assert CB_SKIP    in skip_btn.callback_data,    "Skip button data wrong"
    print(f"  [OK] 인라인 키보드: {len(rows)}행, 버튼=[{approve_btn.text}] [{edit_btn.text}] [{skip_btn.text}]")

    # 3. 메시지 구성
    msg = build_comment_message({
        "title":             "Never Gonna Give You Up",
        "content_type":      "video",
        "url":               "https://youtu.be/dQw4w9WgXcQ",
        "comment_full":      "정말 레전드 노래!\n\nen: A true legend song!",
        "reasoning":         "친근한 스타일 반영",
        "foreign_lang_name": "English",
    })
    assert "Never Gonna Give" in msg, "Title missing from message"
    assert "레전드 노래" in msg,        "Comment missing from message"
    print(f"  [OK] 메시지 구성: {len(msg)}자")
    print()
    print("---- 메시지 미리보기 ----")
    print(msg)
    print("-------------------------")

    # 4. WAITING_EDIT 상태 상수
    assert WAITING_EDIT == 1, f"WAITING_EDIT should be 1, got {WAITING_EDIT}"
    print(f"\n  [OK] WAITING_EDIT 상수: {WAITING_EDIT}")

    print("\n[OK] 모든 Phase 4 Mock 테스트 통과!")


def run_live_test():
    """실제 봇 토큰으로 테스트 메시지를 전송한다."""
    import asyncio
    import config
    from db.database import get_db_manager
    from auth.oauth import YouTubeAuthManager
    from telegram_bot.poster import CommentPoster
    from telegram_bot.bot import TelegramManager

    print("=" * 55)
    print("  Phase 4 Live Test - 봇 메시지 전송 테스트")
    print("=" * 55)

    db = get_db_manager(config.DB_PATH)
    auth_mgr = YouTubeAuthManager(
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
        token_path=config.TOKEN_PATH,
        redirect_uri=config.GOOGLE_REDIRECT_URI,
    )
    yt = auth_mgr.get_youtube_client()
    poster = CommentPoster(youtube_service=yt, db=db)
    tg = TelegramManager(
        bot_token=config.TELEGRAM_BOT_TOKEN,
        chat_id=config.TELEGRAM_CHAT_ID,
        db=db,
        poster=poster,
    )
    tg.build_app()

    async def _send():
        success = await tg.send_comment_draft(
            db_comment_id=9999,
            content_id="dQw4w9WgXcQ",
            content_type="video",
            channel_id="UC_TEST",
            comment_full="정말 레전드 노래!\n\nen: A true legend song!",
            title="[TEST] Never Gonna Give You Up",
            url="https://youtu.be/dQw4w9WgXcQ",
            foreign_lang_name="English",
            reasoning="Phase 4 통합 테스트용 메시지",
        )
        print(f"  전송 결과: {'성공' if success else '실패'}")

    asyncio.run(_send())
    print("\n[OK] 텔레그램에서 메시지와 버튼을 확인하세요.")
    print("     이후 폴링을 시작하려면 'python main.py'를 실행하세요.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    if args.mock:
        run_mock_test()
    elif args.live:
        run_live_test()
    else:
        print("사용법: python test_phase4.py --mock")
        print("        python test_phase4.py --live")
        sys.exit(1)
