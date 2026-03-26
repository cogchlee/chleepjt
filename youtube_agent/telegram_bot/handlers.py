"""
telegram_bot/handlers.py
========================
Telegram 봇 핸들러 모음 — Human-in-the-Loop 승인 프로세스.

흐름도:
  [에이전트가 댓글 초안 전송]
        ↓ 인라인 버튼 3개
  ┌─────────────┬──────────────┬──────────────┐
  │ ✅ 그대로 게시 │ ✍ 직접 수정  │ ⏩ 건너뛰기  │
  └──────┬──────┴──────┬───────┴──────┬───────┘
         ↓              ↓              ↓
    YouTube 게시   텍스트 입력 대기  DB=skipped
    DB=posted      → 수정 후 게시    알림 전송
    알림 전송       DB=posted

ConversationHandler 상태:
  WAITING_EDIT  - 사용자의 수정 텍스트 입력 대기
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from db.database import DatabaseManager
from telegram_bot.poster import CommentPoster
from utils.logger import get_logger

log = get_logger("youtube_agent")

# ── ConversationHandler 상태 ──
WAITING_EDIT = 1

# ── Callback 데이터 접두사 ──
CB_APPROVE = "approve"   # approve:{db_comment_id}:{content_id}
CB_EDIT    = "edit"      # edit:{db_comment_id}:{content_id}
CB_SKIP    = "skip"      # skip:{db_comment_id}:{content_id}

# context.user_data 키
KEY_PENDING = "pending_comment"   # dict: {db_comment_id, content_id, content_type, channel_id}


def _parse_callback(data: str) -> tuple[str, int, str]:
    """
    'action:db_comment_id:content_id' 형식의 callback_data를 파싱한다.
    Returns: (action, db_comment_id, content_id)
    """
    parts = data.split(":", 2)
    action = parts[0] if len(parts) > 0 else ""
    db_id  = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    cid    = parts[2] if len(parts) > 2 else ""
    return action, db_id, cid


def build_approval_keyboard(db_comment_id: int, content_id: str) -> InlineKeyboardMarkup:
    """댓글 초안 승인용 인라인 키보드를 생성한다."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ 그대로 게시",
                callback_data=f"{CB_APPROVE}:{db_comment_id}:{content_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                "✍️ 직접 수정",
                callback_data=f"{CB_EDIT}:{db_comment_id}:{content_id}",
            ),
            InlineKeyboardButton(
                "⏩ 건너뛰기",
                callback_data=f"{CB_SKIP}:{db_comment_id}:{content_id}",
            ),
        ],
    ])


def build_comment_message(result_dict: dict) -> str:
    """
    Telegram 전송용 댓글 초안 메시지를 구성한다.

    Args:
        result_dict: {
            'title': str, 'content_type': str, 'url': str,
            'comment_full': str, 'reasoning': str,
            'foreign_lang_name': str
        }
    """
    type_icon = {"video": "🎬", "short": "📱", "community": "📢"}.get(
        result_dict.get("content_type", ""), "🎬"
    )
    lines = [
        f"*📝 댓글 초안 검토*",
        f"",
        f"{type_icon} *{_esc(result_dict.get('title', '')[:50])}*",
        f"🌐 `{result_dict.get('foreign_lang_name', 'English')}` 병기",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━",
        result_dict.get("comment_full", ""),
        f"━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"💡 _{_esc(result_dict.get('reasoning', '')[:80])}_",
        f"",
        f"🔗 {result_dict.get('url', '')}",
    ]
    return "\n".join(lines)


def _esc(text: str) -> str:
    """MarkdownV2 특수문자 이스케이프 (간단 버전)."""
    # Telegram MarkdownV1에서는 _ * ` [ 만 이스케이프
    for ch in ("_", "*", "[", "`"):
        text = text.replace(ch, f"\\{ch}")
    return text


# ──────────────────────────────────────────────
# 핸들러 클래스
# ──────────────────────────────────────────────

class ApprovalHandlers:
    """
    댓글 승인/수정/건너뛰기 핸들러를 제공한다.

    Args:
        db:             DatabaseManager
        poster:         CommentPoster
        allowed_chat_id: 허용된 Telegram chat ID (보안 필터)
    """

    def __init__(
        self,
        db: DatabaseManager,
        poster: CommentPoster,
        allowed_chat_id: int,
    ):
        self._db = db
        self._poster = poster
        self._allowed = allowed_chat_id

    # ── 보안 필터 ──
    def _is_authorized(self, update: Update) -> bool:
        chat_id = (
            update.effective_chat.id if update.effective_chat else None
        )
        if chat_id != self._allowed:
            log.warning("[Handlers] 미인가 접근 차단. chat_id=%s", chat_id)
            return False
        return True

    # ── /start 명령어 ──
    async def cmd_start(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._is_authorized(update):
            return
        total = self._db.get_setting("total_comments_posted", "0")
        await update.message.reply_text(
            f"🤖 *YouTube Personal Agent* 가동 중!\n\n"
            f"총 게시 댓글: *{total}*개\n"
            f"새 콘텐츠가 발견되면 자동으로 알림을 보내드립니다.",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── /status 명령어 ──
    async def cmd_status(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._is_authorized(update):
            return
        total = self._db.get_setting("total_comments_posted", "0")
        with self._db.get_connection() as conn:
            pending = conn.execute(
                "SELECT COUNT(*) as cnt FROM comments_log WHERE status='pending'"
            ).fetchone()["cnt"]
        await update.message.reply_text(
            f"📊 *에이전트 상태*\n\n"
            f"✅ 총 게시 완료: *{total}*개\n"
            f"⏳ 승인 대기 중: *{pending}*개",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── 승인 버튼 ──
    async def cb_approve(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if not self._is_authorized(update):
            await query.answer("접근 권한이 없습니다.")
            return
        await query.answer("게시 중...")

        _, db_id, content_id = _parse_callback(query.data)
        pending = _get_pending(ctx, db_id, content_id)
        if not pending:
            await query.edit_message_text("⚠️ 요청 정보를 찾을 수 없습니다.")
            return

        success, msg = self._poster.post_comment(
            content_id=pending["content_id"],
            content_type=pending["content_type"],
            channel_id=pending["channel_id"],
            comment_text=pending["comment_full"],
            db_comment_id=db_id,
        )
        if success:
            self._db.update_comment_status(db_id, "posted")
            await query.edit_message_text(
                f"✅ *게시 완료!*\n\n"
                f"🎬 {pending.get('title', '')[:45]}\n\n"
                f"📝 {pending.get('comment_full', '')[:150]}",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await query.edit_message_text(
                f"❌ *게시 실패*\n\n{msg}",
                parse_mode=ParseMode.MARKDOWN,
            )
        _clear_pending(ctx, db_id)

    # ── 수정 버튼 ──
    async def cb_edit(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """수정 버튼 클릭 → WAITING_EDIT 상태로 진입."""
        query = update.callback_query
        if not self._is_authorized(update):
            await query.answer("접근 권한이 없습니다.")
            return ConversationHandler.END
        await query.answer()

        _, db_id, content_id = _parse_callback(query.data)
        pending = _get_pending(ctx, db_id, content_id)

        await query.edit_message_text(
            f"✍️ *직접 수정 모드*\n\n"
            f"수정할 댓글 내용을 입력하세요.\n"
            f"_(그대로 게시할 최종 텍스트를 입력하세요. /cancel 로 취소)_\n\n"
            f"*현재 초안:*\n"
            f"```\n{pending.get('comment_full', '') if pending else '(알 수 없음)'}\n```",
            parse_mode=ParseMode.MARKDOWN,
        )

        # 상태 저장 (ConversationHandler가 메시지를 기다림)
        if ctx.user_data is not None:
            ctx.user_data["edit_db_id"] = db_id
            ctx.user_data["edit_content_id"] = content_id
        return WAITING_EDIT

    # ── 수정 텍스트 수신 ──
    async def msg_receive_edit(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """WAITING_EDIT 상태에서 사용자 텍스트를 받아 게시한다."""
        if not self._is_authorized(update):
            return ConversationHandler.END

        new_text = update.message.text.strip()
        if not new_text:
            await update.message.reply_text("빈 메시지입니다. 다시 입력하거나 /cancel 하세요.")
            return WAITING_EDIT

        db_id      = ctx.user_data.get("edit_db_id", 0) if ctx.user_data else 0
        content_id = ctx.user_data.get("edit_content_id", "") if ctx.user_data else ""
        pending    = _get_pending(ctx, db_id, content_id)

        if not pending:
            await update.message.reply_text("⚠️ 요청 정보가 만료됐습니다.")
            return ConversationHandler.END

        success, msg = self._poster.post_comment(
            content_id=pending["content_id"],
            content_type=pending["content_type"],
            channel_id=pending["channel_id"],
            comment_text=new_text,
            db_comment_id=db_id,
        )
        if success:
            self._db.update_comment_status(db_id, "posted")
            await update.message.reply_text(
                f"✅ *수정 후 게시 완료!*\n\n📝 {new_text[:150]}",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(f"❌ 게시 실패: {msg}")

        _clear_pending(ctx, db_id)
        return ConversationHandler.END

    # ── 건너뛰기 버튼 ──
    async def cb_skip(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if not self._is_authorized(update):
            await query.answer("접근 권한이 없습니다.")
            return
        await query.answer("건너뜁니다.")

        _, db_id, content_id = _parse_callback(query.data)
        pending = _get_pending(ctx, db_id, content_id)

        self._db.update_comment_status(db_id, "rejected")
        if pending:
            self._db.mark_content_processed(
                pending["content_id"],
                pending["channel_id"],
                pending["content_type"],
            )

        await query.edit_message_text(
            f"⏩ *건너뜀*\n\n"
            f"🎬 {pending.get('title', '')[:45] if pending else content_id}\n"
            f"이 콘텐츠는 목록에서 제거됩니다.",
            parse_mode=ParseMode.MARKDOWN,
        )
        _clear_pending(ctx, db_id)

    # ── /cancel 명령어 (ConversationHandler 탈출) ──
    async def cmd_cancel(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        await update.message.reply_text("❎ 수정이 취소됐습니다.")
        return ConversationHandler.END


# ──────────────────────────────────────────────
# Pending 상태 관리 (context.bot_data 공유 저장소)
# ──────────────────────────────────────────────

def store_pending(
    ctx: ContextTypes.DEFAULT_TYPE,
    db_comment_id: int,
    content_id: str,
    content_type: str,
    channel_id: str,
    comment_full: str,
    title: str,
    foreign_lang_name: str,
) -> None:
    """
    댓글 초안 메타데이터를 bot_data에 저장한다 (재시작 전까지 유지).
    키: 'pending_{db_comment_id}'
    """
    if ctx.bot_data is None:
        return
    key = f"pending_{db_comment_id}"
    ctx.bot_data[key] = {
        "content_id": content_id,
        "content_type": content_type,
        "channel_id": channel_id,
        "comment_full": comment_full,
        "title": title,
        "foreign_lang_name": foreign_lang_name,
        "db_comment_id": db_comment_id,
    }


def _get_pending(
    ctx: ContextTypes.DEFAULT_TYPE,
    db_id: int,
    content_id: str,
) -> dict | None:
    """bot_data에서 pending 정보를 조회한다."""
    if ctx.bot_data is None:
        return None
    return ctx.bot_data.get(f"pending_{db_id}")


def _clear_pending(ctx: ContextTypes.DEFAULT_TYPE, db_id: int) -> None:
    """처리 완료된 pending 정보를 삭제한다."""
    if ctx.bot_data:
        ctx.bot_data.pop(f"pending_{db_id}", None)
