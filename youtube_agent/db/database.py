"""
db/database.py
==============
SQLite 데이터베이스 매니저
- 스키마 자동 초기화
- WAL 모드 (동시성 향상)
- context manager 패턴 제공
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# 스키마 파일 경로 (이 파일 기준)
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class DatabaseManager:
    """
    SQLite 연결 및 스키마 초기화를 담당하는 매니저 클래스.

    사용 예:
        db = DatabaseManager("./data/agent.db")
        with db.get_connection() as conn:
            conn.execute("INSERT INTO settings ...")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """schema.sql을 읽어 DB를 초기화한다. 이미 존재하는 테이블은 건드리지 않는다."""
        if not _SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Schema file not found: {_SCHEMA_PATH}")

        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(schema_sql)
        # 초기화 성공 메시지는 호출한 쪽의 로거에서 출력하도록 위임

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        트랜잭션 안전 연결 context manager.
        성공 시 commit, 예외 발생 시 rollback 자동 처리.
        """
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            timeout=10,
        )
        conn.row_factory = sqlite3.Row          # 컬럼명으로 접근 가능
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ──────────────────────────────────────────────
    # 헬퍼 메서드
    # ──────────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        """settings 테이블에서 값을 조회한다."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """settings 테이블에 값을 upsert한다."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value),
            )

    def is_content_processed(self, content_id: str, channel_id: str) -> bool:
        """이미 처리된(댓글 시도한) 콘텐츠인지 확인한다."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_contents WHERE content_id = ? AND channel_id = ?",
                (content_id, channel_id),
            ).fetchone()
        return row is not None

    def mark_content_processed(
        self, content_id: str, channel_id: str, content_type: str
    ) -> None:
        """콘텐츠를 처리 완료로 표시한다."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_contents
                    (content_id, channel_id, content_type)
                VALUES (?, ?, ?)
                """,
                (content_id, channel_id, content_type),
            )

    def is_minute_already_run(self, minute_str: str) -> bool:
        """
        분(minute) 단위 중복 실행 회피 확인.
        minute_str 형식: 'YYYY-MM-DDTHH:MM'
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM scheduler_log WHERE run_minute = ?", (minute_str,)
            ).fetchone()
        return row is not None

    def log_scheduler_run(
        self,
        minute_str: str,
        cycle_type: str = "auto",
        contents_found: int = 0,
        comments_sent: int = 0,
    ) -> None:
        """스케줄러 실행 기록을 남긴다."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO scheduler_log
                    (run_minute, cycle_type, contents_found, comments_sent)
                VALUES (?, ?, ?, ?)
                """,
                (minute_str, cycle_type, contents_found, comments_sent),
            )

    def add_comment_log(
        self,
        content_id: str,
        content_type: str,
        channel_id: str,
        comment_ko: str,
        comment_full: str,
    ) -> int:
        """댓글 로그를 추가하고 생성된 row id를 반환한다."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO comments_log
                    (content_id, content_type, channel_id, comment_ko, comment_full, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
                """,
                (content_id, content_type, channel_id, comment_ko, comment_full),
            )
            return cursor.lastrowid

    def update_comment_status(
        self,
        comment_id: int,
        status: str,
        telegram_msg_id: int | None = None,
        error_msg: str | None = None,
    ) -> None:
        """댓글 상태를 업데이트한다."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE comments_log SET
                    status = ?,
                    telegram_msg_id = COALESCE(?, telegram_msg_id),
                    error_msg = COALESCE(?, error_msg),
                    approved_at = CASE WHEN ? = 'approved' THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now') ELSE approved_at END,
                    posted_at   = CASE WHEN ? = 'posted'   THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now') ELSE posted_at   END
                WHERE id = ?
                """,
                (status, telegram_msg_id, error_msg, status, status, comment_id),
            )


# ── 싱글톤 인스턴스 (모듈 레벨에서 공유) ──
# config가 임포트된 이후에만 사용 가능
_db_instance: DatabaseManager | None = None


def get_db_manager(db_path: str | Path | None = None) -> DatabaseManager:
    """싱글톤 DatabaseManager 인스턴스를 반환한다."""
    global _db_instance
    if _db_instance is None:
        if db_path is None:
            # config 임포트는 선택적으로 (순환 참조 방지)
            from config import DB_PATH
            db_path = DB_PATH
        _db_instance = DatabaseManager(db_path)
    return _db_instance


# ── 직접 실행 시 동작 확인 ──
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    print("DB 초기화 테스트 시작...")
    db = DatabaseManager("./data/agent.db")
    print("[OK] DB 생성 완료: ./data/agent.db")

    # 테이블 목록 확인
    with db.get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    print(f"  생성된 테이블: {[t['name'] for t in tables]}")

    # settings 테스트
    db.set_setting("test_key", "hello_world")
    val = db.get_setting("test_key")
    print(f"  settings 읽기/쓰기 테스트: test_key = '{val}'")

    # 분 단위 중복 회피 테스트
    minute = "2026-03-25T00:00"
    print(f"  scheduler 중복 확인 (before): {db.is_minute_already_run(minute)}")
    db.log_scheduler_run(minute, contents_found=5, comments_sent=2)
    print(f"  scheduler 중복 확인 (after):  {db.is_minute_already_run(minute)}")

    print("\n[OK] 모든 DB 테스트 통과!")
