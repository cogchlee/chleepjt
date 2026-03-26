"""
telegram_bot/bot.py
===================
Telegram Application 초기화 및 핸들러 등록.
에이전트 스케줄러(Phase 5)가 이 모듈을 통해 댓글 초안을 전송한다.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from db.database import DatabaseManager
from telegram_bot.handlers import (
    ApprovalHandlers,
    CB_APPROVE,
    CB_EDIT,
    CB_SKIP,
    WAITING_EDIT,
    build_approval_keyboard,
    build_comment_message,
    store_pending,
)
from telegram_bot.poster import CommentPoster
from utils.logger import get_logger

log = get_logger("youtube_agent")


class TelegramManager:
    """
    Telegram 봇 애플리케이션 및 댓글 초안 전송 관리자.

    담당:
      1. Application 빌드 및 핸들러 등록
      2. 댓글 초안 메시지 전송 (에이전트 → 사용자)
      3. 폴링 루프 실행/중지

    Args:
        bot_token:     Telegram 봇 토큰
        chat_id:       승인을 받을 사용자 chat ID
        db:            DatabaseManager
        poster:        CommentPoster
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: int,
        db: DatabaseManager,
        poster: CommentPoster,
    ):
        self._chat_id = chat_id
        self._db = db
        self._poster = poster

        self._handlers = ApprovalHandlers(
            db=db,
            poster=poster,
            allowed_chat_id=chat_id,
        )

        self._app: Optional[Application] = None
        self._token = bot_token

    # ──────────────────────────────────────────────
    # Application 빌드
    # ──────────────────────────────────────────────

    def build_app(self) -> Application:
        """
        Telegram Application을 빌드하고 모든 핸들러를 등록한다.
        이 메서드는 폴링 시작 전에 한 번만 호출해야 한다.
        """
        app = (
            Application.builder()
            .token(self._token)
            .build()
        )

        h = self._handlers

        # ── 일반 명령어 ──
        app.add_handler(CommandHandler("start", h.cmd_start))
        app.add_handler(CommandHandler("status", h.cmd_status))

        # ── ConversationHandler: 수정 플로우 ──
        # WAITING_EDIT 상태에서만 텍스트 입력을 처리
        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(h.cb_edit, pattern=f"^{CB_EDIT}:")
            ],
            states={
                WAITING_EDIT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        h.msg_receive_edit,
                    )
                ],
            },
            fallbacks=[CommandHandler("cancel", h.cmd_cancel)],
            per_message=False,      # per_chat 기준으로 상태 관리
            allow_reentry=True,
        )
        app.add_handler(conv_handler)

        # ── 일반 콜백 핸들러 (승인/건너뛰기) ──
        app.add_handler(CallbackQueryHandler(h.cb_approve, pattern=f"^{CB_APPROVE}:"))
        app.add_handler(CallbackQueryHandler(h.cb_skip,    pattern=f"^{CB_SKIP}:"))

        self._app = app
        log.info("[TelegramManager] Application 빌드 완료.")
        return app

    # ──────────────────────────────────────────────
    # 댓글 초안 전송 (에이전트 → 사용자)
    # ──────────────────────────────────────────────

    async def send_comment_draft(
        self,
        db_comment_id: int,
        content_id: str,
        content_type: str,
        channel_id: str,
        comment_full: str,
        title: str,
        url: str,
        foreign_lang_name: str,
        reasoning: str = "",
    ) -> bool:
        """
        댓글 초안을 인라인 버튼과 함께 사용자에게 전송한다.
        스케줄러(Phase 5)에서 댓글 생성 후 이 메서드를 호출한다.

        Returns:
            True = 전송 성공
        """
        if self._app is None:
            log.error("[TelegramManager] app이 초기화되지 않았습니다.")
            return False

        # bot_data에 pending 저장 (승인 버튼 클릭 시 참조)
        store_pending(
            ctx=self._app.bot_data_context({}),   # 임시 ctx 없이 직접 저장
            db_comment_id=db_comment_id,
            content_id=content_id,
            content_type=content_type,
            channel_id=channel_id,
            comment_full=comment_full,
            title=title,
            foreign_lang_name=foreign_lang_name,
        )
        # bot_data에 직접 저장 (Application 레벨 공유 저장소)
        self._app.bot_data[f"pending_{db_comment_id}"] = {
            "content_id": content_id,
            "content_type": content_type,
            "channel_id": channel_id,
            "comment_full": comment_full,
            "title": title,
            "foreign_lang_name": foreign_lang_name,
            "db_comment_id": db_comment_id,
        }

        text = build_comment_message({
            "title": title,
            "content_type": content_type,
            "url": url,
            "comment_full": comment_full,
            "reasoning": reasoning,
            "foreign_lang_name": foreign_lang_name,
        })
        keyboard = build_approval_keyboard(db_comment_id, content_id)

        try:
            from telegram.constants import ParseMode
            await self._app.bot.send_message(
                chat_id=self._chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            # DB 상태: pending → approved (텔레그램 전송 완료)
            self._db.update_comment_status(db_comment_id, "approved")
            log.info(
                "[TelegramManager] 댓글 초안 전송 완료. db_id=%d, content=%s",
                db_comment_id, content_id,
            )
            return True
        except Exception as e:
            log.error("[TelegramManager] 메시지 전송 실패: %s", e, exc_info=True)
            return False

    async def send_notification(self, text: str) -> None:
        """일반 알림 메시지를 전송한다 (게시 성공/실패 결과 등)."""
        if self._app is None:
            return
        try:
            await self._app.bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode="Markdown",
            )
        except Exception as e:
            log.error("[TelegramManager] 알림 전송 실패: %s", e)

    # ──────────────────────────────────────────────
    # 폴링 루프
    # ──────────────────────────────────────────────

    def run_polling(self) -> None:
        """
        동기 방식으로 폴링 루프를 시작한다.
        Phase 5 스케줄러와 함께 asyncio로 통합 시 `run_async_polling()` 사용.
        """
        if self._app is None:
            self.build_app()
        log.info("[TelegramManager] 폴링 시작...")
        self._app.run_polling(drop_pending_updates=True)

    async def run_async_polling(self) -> None:
        """
        비동기 폴링 루프. asyncio.gather()로 스케줄러와 동시 실행 가능.
        """
        if self._app is None:
            self.build_app()
        log.info("[TelegramManager] 비동기 폴링 시작...")
        async with self._app:
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)
            # 외부에서 stop() 호출될 때까지 대기
            await asyncio.Event().wait()

    async def stop(self) -> None:
        """폴링을 종료한다."""
        if self._app and self._app.updater:
            await self._app.updater.stop()
            await self._app.stop()
            log.info("[TelegramManager] 폴링 종료.")
