"""
scheduler/scheduler.py
======================
3시간 주기 비동기 스케줄러 — Phase 5 핵심 모듈.

설계 원칙:
  1. 3시간 기본 주기 + 분(Minute) 단위 랜덤 오프셋 (이전 실행 분과 중복 방지)
  2. 분 단위 Jitter (1~30초) 추가 → 봇 탐지 회피
  3. KST 에티켓 시간 준수 (기본: 01:00~06:00 KST 구간 동작 중단)
  4. YouTube API 할당량 소진 시 6시간 대기 후 재시도
  5. 네트워크/인증 오류 시 지수 백오프 재시도 (최대 3회)
  6. asyncio 기반 → Telegram 폴링과 gather() 동시 실행
  7. SQLite scheduler_log로 분 단위 중복 실행 원천 차단
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.comment_generator import CommentGenerator
from db.database import DatabaseManager
from telegram_bot.bot import TelegramManager
from youtube.content_manager import ContentManager
from utils.logger import get_logger

log = get_logger("youtube_agent")

# ── 한국 시간대 ──
KST = pytz.timezone("Asia/Seoul")

# ── 기본 설정 상수 ──
_DEFAULT_INTERVAL_HOURS  = 3
_BLACKOUT_START_HOUR     = 1   # KST 01:00부터
_BLACKOUT_END_HOUR       = 6   # KST 06:00까지 (이 시각은 허용)
_JITTER_MIN_SEC          = 1
_JITTER_MAX_SEC          = 30
_QUOTA_WAIT_HOURS        = 6   # 할당량 소진 시 대기
_APPROVAL_TIMEOUT_HOURS  = 1   # 미승인 pending 재시도 대기
_MAX_NETWORK_RETRY       = 3


class AgentScheduler:
    """
    YouTube Personal Agent 전체 사이클 스케줄러.

    Args:
        content_manager:  ContentManager 인스턴스
        generator:        CommentGenerator 인스턴스
        tg_manager:       TelegramManager 인스턴스
        db:               DatabaseManager 인스턴스
        target_channels:  대상 채널 ID 리스트
        lang_code:        댓글 외국어 코드 (기본: 'en')
        interval_hours:   기본 실행 주기 (기본: 3시간)
        blackout_start:   에티켓 시작 시각 KST (기본: 1)
        blackout_end:     에티켓 종료 시각 KST (기본: 6)
    """

    def __init__(
        self,
        content_manager: ContentManager,
        generator: CommentGenerator,
        tg_manager: TelegramManager,
        db: DatabaseManager,
        target_channels: list[str],
        lang_code: str = "en",
        interval_hours: int = _DEFAULT_INTERVAL_HOURS,
        blackout_start: int = _BLACKOUT_START_HOUR,
        blackout_end: int = _BLACKOUT_END_HOUR,
    ):
        self._cm = content_manager
        self._gen = generator
        self._tg = tg_manager
        self._db = db
        self._channels = target_channels
        self._lang = lang_code
        self._interval_hours = interval_hours
        self._blackout_start = blackout_start
        self._blackout_end = blackout_end
        self._stop_event = asyncio.Event()
        self._last_run_minute: Optional[str] = None   # 'HH:MM' 형식

    # ──────────────────────────────────────────────
    # 메인 루프
    # ──────────────────────────────────────────────

    async def run_loop(self) -> None:
        """
        에이전트 메인 실행 루프. asyncio.gather()로 Telegram 폴링과 동시 실행.
        stop() 호출 시 종료된다.
        """
        log.info(
            "[Scheduler] 루프 시작. 주기=%dh, 에티켓=%d~%dKST",
            self._interval_hours,
            self._blackout_start,
            self._blackout_end,
        )
        await self._notify("🤖 YouTube Personal Agent가 시작되었습니다.")

        while not self._stop_event.is_set():
            try:
                await self._run_one_cycle()
            except Exception as e:
                log.error("[Scheduler] 사이클 실행 중 예외: %s", e, exc_info=True)
                await self._notify(f"⚠️ 스케줄러 오류 발생:\n`{e}`\n5분 후 재시도합니다.")
                await self._interruptible_sleep(300)
                continue

            wait_sec = self._calculate_next_wait()
            next_run = datetime.now(tz=KST) + timedelta(seconds=wait_sec)
            log.info(
                "[Scheduler] 다음 실행: %s KST (%.1f분 후)",
                next_run.strftime("%H:%M"),
                wait_sec / 60,
            )
            await self._interruptible_sleep(wait_sec)

        log.info("[Scheduler] 루프 종료.")

    async def stop(self) -> None:
        """루프를 안전하게 종료한다."""
        self._stop_event.set()

    # ──────────────────────────────────────────────
    # 단일 사이클
    # ──────────────────────────────────────────────

    async def _run_one_cycle(self) -> None:
        """
        한 사이클: 에티켓 확인 → 분 중복 확인 → 콘텐츠 수집 → 댓글 생성 → 텔레그램 전송.
        """
        now_kst = datetime.now(tz=KST)

        # ① KST 에티켓 시간 확인
        if self._is_blackout(now_kst):
            log.info(
                "[Scheduler] 에티켓 시간대(%d~%d KST). 실행 건너뜀.",
                self._blackout_start,
                self._blackout_end,
            )
            return

        # ② 분(minute) 단위 중복 실행 방지
        minute_key = now_kst.strftime("%Y-%m-%dT%H:%M")
        if self._db.is_minute_already_run(minute_key):
            log.info("[Scheduler] 이미 이 분(%s)에 실행됨. 건너뜀.", minute_key)
            return

        # ③ Jitter (봇 탐지 회피용 랜덤 딜레이)
        jitter = random.uniform(_JITTER_MIN_SEC, _JITTER_MAX_SEC)
        log.info("[Scheduler] Jitter %.1f초 대기 후 실행...", jitter)
        await asyncio.sleep(jitter)

        contents_found = 0
        comments_sent  = 0

        # ④ 콘텐츠 수집 (채널별)
        for attempt in range(1, _MAX_NETWORK_RETRY + 1):
            try:
                candidates = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._cm.discover_all_channels,
                    self._channels,
                )
                contents_found = len(candidates)
                log.info("[Scheduler] 수집 완료: %d건", contents_found)
                break
            except Exception as e:
                err_str = str(e)
                if "quotaExceeded" in err_str or "quota" in err_str.lower():
                    wait_h = _QUOTA_WAIT_HOURS
                    log.error(
                        "[Scheduler] YouTube API 할당량 소진. %dh 대기.", wait_h
                    )
                    await self._notify(
                        f"⛔ YouTube API 할당량 소진!\n"
                        f"{wait_h}시간 후 자동 재개됩니다."
                    )
                    await self._interruptible_sleep(wait_h * 3600)
                    return
                log.error(
                    "[Scheduler] 콘텐츠 수집 오류 (시도 %d/%d): %s",
                    attempt, _MAX_NETWORK_RETRY, e,
                )
                if attempt == _MAX_NETWORK_RETRY:
                    await self._notify(
                        f"❌ 콘텐츠 수집 실패 (최대 재시도 초과):\n`{e}`"
                    )
                    return
                await asyncio.sleep(2 ** attempt * 10)  # 지수 백오프

        # ⑤ 댓글 생성 → 텔레그램 전송 (후보당 1개씩)
        for item in candidates:
            if self._stop_event.is_set():
                break
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda i=item: self._gen.generate(
                        i, lang_code=self._lang, save_to_db=True
                    ),
                )
                if result is None:
                    log.warning("[Scheduler] 댓글 생성 실패: %s", item.content_id)
                    continue

                sent = await self._tg.send_comment_draft(
                    db_comment_id=result.db_comment_id,
                    content_id=item.content_id,
                    content_type=item.content_type,
                    channel_id=item.channel_id,
                    comment_full=result.comment_full,
                    title=item.title,
                    url=item.url,
                    foreign_lang_name=result.foreign_lang_name,
                    reasoning=result.reasoning,
                )
                if sent:
                    comments_sent += 1
                    log.info(
                        "[Scheduler] 텔레그램 전송 완료: %s", item.content_id
                    )
                # 연속 전송 간 간격 (봇 탐지 회피)
                await asyncio.sleep(random.uniform(2.0, 5.0))

            except Exception as e:
                log.error(
                    "[Scheduler] 댓글 생성/전송 오류: %s — %s", item.content_id, e,
                    exc_info=True,
                )

        # ⑥ 사이클 로그 기록 (분 단위 중복 방지 완성)
        self._db.log_scheduler_run(
            minute_key,
            cycle_type="auto",
            contents_found=contents_found,
            comments_sent=comments_sent,
        )
        self._last_run_minute = now_kst.strftime("%H:%M")
        log.info(
            "[Scheduler] 사이클 완료. 수집=%d, 전송=%d",
            contents_found, comments_sent,
        )

        if contents_found == 0:
            log.info("[Scheduler] 새 콘텐츠 없음.")

    # ──────────────────────────────────────────────
    # 다음 실행 시각 계산
    # ──────────────────────────────────────────────

    def _calculate_next_wait(self) -> float:
        """
        다음 실행까지 대기 시간(초)을 계산한다.

        로직:
          1. 기본 간격 = interval_hours * 3600초
          2. 분(Minute) 랜덤 오프셋: 이전 실행 분과 다른 분을 1~59 중 선택
          3. 에티켓 시간대 진입 예정이면 에티켓 종료 시각까지 추가 대기
        """
        base_sec = self._interval_hours * 3600

        # 이전 실행 분과 다른 랜덤 분 오프셋 선택
        if self._last_run_minute:
            try:
                last_min = int(self._last_run_minute.split(":")[-1])
            except (ValueError, IndexError):
                last_min = -1
            excluded = {last_min}
        else:
            excluded = set()

        available = [m for m in range(0, 60) if m not in excluded]
        chosen_min = random.choice(available)
        # 현재 분과의 차이를 오프셋으로 변환
        now_min = datetime.now(tz=KST).minute
        min_offset_sec = ((chosen_min - now_min) % 60) * 60

        total_wait = base_sec + min_offset_sec

        # 에티켓 시간대 진입 시 추가 대기 계산
        next_run_kst = datetime.now(tz=KST) + timedelta(seconds=total_wait)
        if self._is_blackout(next_run_kst):
            # 에티켓 종료 시각(blackout_end:00 KST)까지 대기 추가
            end_kst = next_run_kst.replace(
                hour=self._blackout_end, minute=0, second=0, microsecond=0
            )
            if end_kst < next_run_kst:
                end_kst += timedelta(days=1)
            extra = (end_kst - next_run_kst).total_seconds()
            total_wait += extra
            log.info(
                "[Scheduler] 에티켓 시간 회피: %.0f분 추가 대기.", extra / 60
            )

        log.info(
            "[Scheduler] 다음 실행 오프셋: 기본 %dh + 분오프셋 %dm = 총 %.1f분. "
            "(선택 분: %02d)",
            self._interval_hours,
            min_offset_sec // 60,
            total_wait / 60,
            chosen_min,
        )
        return total_wait

    def _is_blackout(self, dt_kst: datetime) -> bool:
        """주어진 KST 시각이 에티켓 중단 구간인지 확인한다."""
        h = dt_kst.hour
        if self._blackout_start <= self._blackout_end:
            return self._blackout_start <= h < self._blackout_end
        else:  # 자정 경계 처리 (ex: 23~06)
            return h >= self._blackout_start or h < self._blackout_end

    # ──────────────────────────────────────────────
    # 미승인 Pending 재시도
    # ──────────────────────────────────────────────

    async def retry_pending(self) -> None:
        """
        1시간 이상 미승인(pending) 상태 댓글을 텔레그램으로 재전송한다.
        사이클 시작 시 호출되거나 별도 태스크로 주기적 실행 가능.
        """
        cutoff = (
            datetime.now(tz=timezone.utc) - timedelta(hours=_APPROVAL_TIMEOUT_HOURS)
        ).strftime("%Y-%m-%dT%H:%M:%S")

        with self._db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, content_id, content_type, channel_id,
                       comment_full, created_at
                FROM comments_log
                WHERE status = 'pending'
                  AND created_at < ?
                ORDER BY created_at ASC
                LIMIT 3
                """,
                (cutoff,),
            ).fetchall()

        if not rows:
            return

        log.info("[Scheduler] 미승인 pending %d건 재전송 시도.", len(rows))
        for row in rows:
            try:
                await self._tg.send_comment_draft(
                    db_comment_id=row["id"],
                    content_id=row["content_id"],
                    content_type=row["content_type"],
                    channel_id=row["channel_id"],
                    comment_full=row["comment_full"],
                    title=f"[재전송] {row['content_id']}",
                    url=f"https://www.youtube.com/watch?v={row['content_id']}",
                    foreign_lang_name="English",
                    reasoning="1시간 이상 미승인 상태 — 재전송",
                )
                await asyncio.sleep(2)
            except Exception as e:
                log.error("[Scheduler] pending 재전송 오류: %s", e)

    # ──────────────────────────────────────────────
    # 헬퍼
    # ──────────────────────────────────────────────

    async def _interruptible_sleep(self, seconds: float) -> None:
        """stop_event가 세트되면 즉시 깨어나는 sleep."""
        try:
            await asyncio.wait_for(
                self._stop_event.wait(),
                timeout=seconds,
            )
        except asyncio.TimeoutError:
            pass

    async def _notify(self, text: str) -> None:
        """TelegramManager를 통해 관리자에게 알림을 전송한다."""
        try:
            await self._tg.send_notification(text)
        except Exception as e:
            log.error("[Scheduler] 알림 전송 실패: %s", e)
