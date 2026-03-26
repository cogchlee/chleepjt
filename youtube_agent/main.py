"""
main.py
=======
YouTube Personal Agent - 최종 통합 진입점 (Phase 1 ~ 5)

실행 흐름:
  1. 환경 변수 로드 & 검증 (config.py)
  2. DB 초기화 (db/database.py)
  3. YouTube OAuth (auth/oauth.py)
  4. Gemini 초기화 (ai/)
  5. Telegram 봇 빌드 (telegram_bot/)
  6. ContentManager 빌드 (youtube/)
  7. AgentScheduler + Telegram 폴링 asyncio.gather() 동시 실행

종료:
  - Ctrl+C (SIGINT) 또는 SIGTERM → 스케줄러와 폴링 모두 정상 종료
"""

import asyncio
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import google.generativeai as genai

import config
from ai.comment_generator import CommentGenerator
from ai.style_learner import StyleLearner
from auth.oauth import YouTubeAuthManager
from db.database import get_db_manager
from scheduler.scheduler import AgentScheduler
from telegram_bot.bot import TelegramManager
from telegram_bot.poster import CommentPoster
from utils.logger import setup_logger, get_logger
from youtube.content_manager import ContentManager


# ──────────────────────────────────────────────
# 초기화
# ──────────────────────────────────────────────

def build_all_modules():
    """
    모든 모듈을 초기화하고 반환한다.
    순서: logger → DB → YouTube OAuth → Gemini → AI → Telegram → ContentManager → Scheduler
    """
    setup_logger(
        "youtube_agent",
        log_dir=str(config.LOG_DIR),
        use_json=False,   # Oracle Cloud 배포 시 True로 변경
    )
    log = get_logger("youtube_agent")
    log.info("=" * 55)
    log.info("  YouTube Personal Agent v1.0  (Phase 1~5)")
    log.info("=" * 55)

    # DB
    db = get_db_manager(config.DB_PATH)
    log.info("[Init] DB 준비 완료: %s", config.DB_PATH)

    # YouTube OAuth
    auth_mgr = YouTubeAuthManager(
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
        token_path=config.TOKEN_PATH,
        redirect_uri=config.GOOGLE_REDIRECT_URI,
    )
    yt = auth_mgr.get_youtube_client()
    log.info("[Init] YouTube OAuth 완료.")

    # Gemini
    genai.configure(api_key=config.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(config.GEMINI_MODEL)
    log.info("[Init] Gemini 모델 준비: %s", config.GEMINI_MODEL)

    # AI 모듈
    style_learner = StyleLearner(
        youtube_service=yt,
        gemini_model=gemini_model,
        db=db,
        my_channel_id=config.MY_CHANNEL_ID,
    )
    generator = CommentGenerator(
        gemini_model=gemini_model,
        style_learner=style_learner,
        db=db,
        default_lang="en",   # 채널 언어 자동 감지 또는 고정
        temperature=0.75,
    )
    log.info("[Init] AI 모듈 준비 완료.")

    # Telegram
    poster = CommentPoster(youtube_service=yt, db=db)
    tg_manager = TelegramManager(
        bot_token=config.TELEGRAM_BOT_TOKEN,
        chat_id=config.TELEGRAM_CHAT_ID,
        db=db,
        poster=poster,
    )
    tg_manager.build_app()
    log.info("[Init] TelegramManager 준비 완료.")

    # ContentManager
    content_manager = ContentManager(
        youtube_service=yt,
        db=db,
        max_videos=20,
        max_posts=10,
        include_community=True,
        cookies_path=config.DATA_DIR / "cookies.json",
        headless=True,
    )

    # Scheduler
    scheduler = AgentScheduler(
        content_manager=content_manager,
        generator=generator,
        tg_manager=tg_manager,
        db=db,
        target_channels=config.TARGET_CHANNEL_IDS,
        lang_code="en",
        interval_hours=config.SCHEDULE_INTERVAL_HOURS,
        blackout_start=config.ETIQUETTE_START_HOUR
            if config.ETIQUETTE_START_HOUR > config.ETIQUETTE_END_HOUR
            else 1,     # 새벽 에티켓 구간: 01~06 KST
        blackout_end=6,
    )
    log.info(
        "[Init] AgentScheduler 준비 완료. 주기=%dh, 에티켓=01~06 KST",
        config.SCHEDULE_INTERVAL_HOURS,
    )

    return tg_manager, scheduler


# ──────────────────────────────────────────────
# 메인 비동기 루프
# ──────────────────────────────────────────────

async def async_main() -> None:
    log = get_logger("youtube_agent")
    tg_manager, scheduler = build_all_modules()

    loop = asyncio.get_running_loop()

    # 시그널 핸들러: Ctrl+C / SIGTERM → 정상 종료
    async def _shutdown(sig_name: str):
        log.info("[Main] 종료 신호 수신: %s. 정상 종료 중...", sig_name)
        await scheduler.stop()
        await tg_manager.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig,
                lambda s=sig.name: asyncio.create_task(_shutdown(s)),
            )
        except (NotImplementedError, AttributeError):
            # Windows는 add_signal_handler 미지원 → KeyboardInterrupt로 처리
            pass

    log.info("[Main] 텔레그램 폴링 + 스케줄러 동시 시작.")
    try:
        await asyncio.gather(
            tg_manager.run_async_polling(),
            scheduler.run_loop(),
        )
    except asyncio.CancelledError:
        log.info("[Main] asyncio 태스크 취소됨.")
    except KeyboardInterrupt:
        log.info("[Main] KeyboardInterrupt 수신.")
        await scheduler.stop()
        await tg_manager.stop()
    finally:
        log.info("[Main] 에이전트 종료 완료.")


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass  # 이미 내부에서 처리


if __name__ == "__main__":
    main()

