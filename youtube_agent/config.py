"""
config.py
=========
환경 변수 로더 - python-dotenv 기반
필수 변수 누락 시 명확한 에러로 조기 종료.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 기준 .env 파일 로드
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()  # 환경 변수가 이미 주입된 경우 (Docker/Oracle Cloud Functions)


def _require(key: str) -> str:
    """환경 변수가 반드시 존재해야 할 때 사용. 없으면 즉시 종료."""
    value = os.getenv(key, "").strip()
    if not value:
        print(f"[CONFIG ERROR] Required environment variable '{key}' is missing or empty.")
        print(f"  → .env 파일을 확인하거나 .env.example을 참고하여 값을 설정하세요.")
        sys.exit(1)
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _optional_int(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"[CONFIG WARNING] '{key}' must be an integer. Using default: {default}")
        return default


# ──────────────────────────────────────────────
# Google OAuth 2.0
# ──────────────────────────────────────────────
GOOGLE_CLIENT_ID: str = _require("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET: str = _require("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI: str = _optional("GOOGLE_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob")

# ──────────────────────────────────────────────
# YouTube API
# ──────────────────────────────────────────────
YOUTUBE_API_KEY: str = _require("YOUTUBE_API_KEY")
TARGET_CHANNEL_IDS: list[str] = [
    cid.strip()
    for cid in _require("TARGET_CHANNEL_IDS").split(",")
    if cid.strip()
]
MY_CHANNEL_ID: str = _require("MY_CHANNEL_ID")

# ──────────────────────────────────────────────
# Gemini
# ──────────────────────────────────────────────
GEMINI_API_KEY: str = _require("GEMINI_API_KEY")
GEMINI_MODEL: str = _optional("GEMINI_MODEL", "gemini-2.0-flash")

# ──────────────────────────────────────────────
# Telegram
# ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: int = int(_require("TELEGRAM_CHAT_ID"))

# ──────────────────────────────────────────────
# Scheduler
# ──────────────────────────────────────────────
SCHEDULE_INTERVAL_HOURS: int = _optional_int("SCHEDULE_INTERVAL_HOURS", 3)
SCHEDULE_JITTER_MINUTES: int = _optional_int("SCHEDULE_JITTER_MINUTES", 30)
ETIQUETTE_START_HOUR: int = _optional_int("ETIQUETTE_START_HOUR", 8)
ETIQUETTE_END_HOUR: int = _optional_int("ETIQUETTE_END_HOUR", 23)

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
DATA_DIR: Path = Path(_optional("DATA_DIR", "./data"))
LOG_DIR: Path = Path(_optional("LOG_DIR", "./logs"))
DB_PATH: Path = Path(_optional("DB_PATH", str(DATA_DIR / "agent.db")))
TOKEN_PATH: Path = Path(_optional("TOKEN_PATH", str(DATA_DIR / "token.json")))

# 런타임에 디렉토리 자동 생성
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────
# 직접 실행 시 설정값 출력 (디버그용)
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  YouTube Personal Agent - Config Check")
    print("=" * 55)
    print(f"  GOOGLE_CLIENT_ID    : {GOOGLE_CLIENT_ID[:20]}...")
    print(f"  GOOGLE_REDIRECT_URI : {GOOGLE_REDIRECT_URI}")
    print(f"  YOUTUBE_API_KEY     : {YOUTUBE_API_KEY[:10]}...")
    print(f"  TARGET_CHANNEL_IDS  : {TARGET_CHANNEL_IDS}")
    print(f"  MY_CHANNEL_ID       : {MY_CHANNEL_ID}")
    print(f"  GEMINI_MODEL        : {GEMINI_MODEL}")
    print(f"  TELEGRAM_CHAT_ID    : {TELEGRAM_CHAT_ID}")
    print(f"  INTERVAL(hrs)       : {SCHEDULE_INTERVAL_HOURS}")
    print(f"  JITTER(min)         : {SCHEDULE_JITTER_MINUTES}")
    print(f"  ETIQUETTE           : {ETIQUETTE_START_HOUR}:00 ~ {ETIQUETTE_END_HOUR}:00 KST")
    print(f"  DB_PATH             : {DB_PATH.resolve()}")
    print(f"  TOKEN_PATH          : {TOKEN_PATH.resolve()}")
    print("=" * 55)
    print("✅ 모든 필수 환경 변수가 정상적으로 로드되었습니다.")
