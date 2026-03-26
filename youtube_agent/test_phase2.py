"""
test_phase2.py
==============
Phase 2 검증 테스트 스크립트.
실제 YouTube API와 DB를 연결하여 후보군을 출력한다.

사용법:
    python test_phase2.py --channel UCxxxxxx
    python test_phase2.py --channel UCxxxxxx --no-community
    python test_phase2.py --channel UCxxxxxx --no-headless
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from utils.logger import setup_logger, get_logger
from db.database import get_db_manager
from auth.oauth import YouTubeAuthManager
from youtube.content_manager import ContentManager


def print_candidates(candidates):
    """후보 콘텐츠를 가독성 높게 출력한다."""
    if not candidates:
        print("\n  [결과 없음] 작성 후보 콘텐츠가 없습니다.")
        return

    type_icons = {"video": "[V]", "short": "[S]", "community": "[C]"}
    print(f"\n{'='*60}")
    print(f"  작성 후보 콘텐츠: 총 {len(candidates)}건")
    print(f"{'='*60}")
    for i, item in enumerate(candidates, 1):
        icon = type_icons.get(item.content_type, "[?]")
        print(f"\n  {i:02d}. {icon} {item.title[:55]}")
        print(f"      ID      : {item.content_id}")
        print(f"      채널    : {item.channel_id}")
        print(f"      게시일  : {item.published_at}")
        print(f"      URL     : {item.url}")


def main():
    parser = argparse.ArgumentParser(description="Phase 2 콘텐츠 수집 테스트")
    parser.add_argument(
        "--channel",
        type=str,
        nargs="+",
        help="대상 채널 ID (UC...). 기본값: .env의 TARGET_CHANNEL_IDS",
    )
    parser.add_argument(
        "--no-community",
        action="store_true",
        help="커뮤니티 탭 수집 건너뜀 (Selenium 없을 때 사용)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Selenium 브라우저 창 표시 (디버깅용)",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=10,
        help="채널당 최대 수집 영상 수 (기본: 10)",
    )
    args = parser.parse_args()

    # ── 초기화 ──
    setup_logger("youtube_agent", log_dir=str(config.LOG_DIR))
    log = get_logger("youtube_agent")

    channel_ids = args.channel or config.TARGET_CHANNEL_IDS
    if not channel_ids:
        print("[ERROR] 채널 ID를 --channel 옵션으로 지정하거나 .env의 TARGET_CHANNEL_IDS를 설정하세요.")
        sys.exit(1)

    log.info("Phase 2 테스트 시작. 대상 채널: %s", channel_ids)

    db = get_db_manager(config.DB_PATH)

    auth_mgr = YouTubeAuthManager(
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
        token_path=config.TOKEN_PATH,
        redirect_uri=config.GOOGLE_REDIRECT_URI,
    )
    yt = auth_mgr.get_youtube_client()

    mgr = ContentManager(
        youtube_service=yt,
        db=db,
        max_videos=args.max_videos,
        max_posts=5,
        include_community=not args.no_community,
        cookies_path="./data/cookies.json",
        headless=not args.no_headless,
    )

    # ── 수집 ──
    print(f"\n대상 채널 ({len(channel_ids)}개): {channel_ids}")
    print("콘텐츠 수집 중...\n")

    all_candidates = mgr.discover_all_channels(channel_ids)
    print_candidates(all_candidates)

    print(f"\n[완료] 총 후보: {len(all_candidates)}건")
    log.info("Phase 2 테스트 완료. 후보 %d건.", len(all_candidates))


if __name__ == "__main__":
    main()
