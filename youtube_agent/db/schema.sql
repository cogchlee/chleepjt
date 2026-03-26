-- =============================================
-- YouTube Personal Agent - SQLite Schema
-- =============================================

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ------------------------------------
-- 댓글 이력 로그
-- ------------------------------------
CREATE TABLE IF NOT EXISTS comments_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id      TEXT    NOT NULL,                  -- YouTube video/post ID
    content_type    TEXT    NOT NULL CHECK(content_type IN ('video', 'short', 'community')),
    channel_id      TEXT    NOT NULL,                  -- Target channel ID
    comment_ko      TEXT    NOT NULL,                  -- 생성된 한글 댓글
    comment_full    TEXT    NOT NULL,                  -- 한글+외국어 병기 최종 댓글
    status          TEXT    NOT NULL DEFAULT 'pending' -- pending | approved | rejected | posted | failed
                    CHECK(status IN ('pending', 'approved', 'rejected', 'posted', 'failed')),
    telegram_msg_id INTEGER,                           -- 텔레그램 메시지 ID (승인 추적용)
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    approved_at     TEXT,
    posted_at       TEXT,
    error_msg       TEXT                               -- 실패 시 에러 내용
);

CREATE INDEX IF NOT EXISTS idx_comments_content_id ON comments_log(content_id);
CREATE INDEX IF NOT EXISTS idx_comments_status ON comments_log(status);
CREATE INDEX IF NOT EXISTS idx_comments_created_at ON comments_log(created_at);

-- ------------------------------------
-- 스케줄러 실행 로그 (분 단위 중복 회피)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS scheduler_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_minute      TEXT    NOT NULL UNIQUE,           -- 'YYYY-MM-DDTHH:MM' 형식 (분 단위 유일성 보장)
    cycle_type      TEXT    NOT NULL DEFAULT 'auto',   -- auto | manual
    contents_found  INTEGER NOT NULL DEFAULT 0,
    comments_sent   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_scheduler_run_minute ON scheduler_log(run_minute);

-- ------------------------------------
-- 스타일 학습용 내 과거 댓글 캐시
-- ------------------------------------
CREATE TABLE IF NOT EXISTS style_samples (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id      TEXT    NOT NULL UNIQUE,           -- YouTube Comment ID
    video_id        TEXT    NOT NULL,
    comment_text    TEXT    NOT NULL,
    like_count      INTEGER NOT NULL DEFAULT 0,
    published_at    TEXT    NOT NULL,
    fetched_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ------------------------------------
-- 처리된 콘텐츠 (재댓글 방지)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS processed_contents (
    content_id      TEXT    NOT NULL,
    channel_id      TEXT    NOT NULL,
    content_type    TEXT    NOT NULL,
    processed_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (content_id, channel_id)
);

-- ------------------------------------
-- 전역 설정 (Key-Value)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    key             TEXT    PRIMARY KEY,
    value           TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- 기본 설정 초기화
INSERT OR IGNORE INTO settings (key, value) VALUES
    ('style_last_fetched', ''),
    ('agent_version', '1.0.0'),
    ('total_comments_posted', '0');
