"""
utils/logger.py
===============
구조화된 로깅 모듈 - Oracle Cloud 24/7 운영 환경 최적화
- RotatingFileHandler: 일별 교체, 최대 30일 보관
- StreamHandler: 콘솔 출력 (systemd journal 수집 대응)
- JSON 포맷 옵션: Oracle Cloud Logging 서비스 연동 가능
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """Oracle Cloud Logging 서비스와 호환되는 JSON 구조화 로그 포맷터."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "funcName": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        return json.dumps(log_obj, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """콘솔 및 일반 파일용 가독성 높은 포맷터."""

    LEVEL_COLORS = {
        "DEBUG":    "\033[36m",   # Cyan
        "INFO":     "\033[32m",   # Green
        "WARNING":  "\033[33m",   # Yellow
        "ERROR":    "\033[31m",   # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool = False):
        super().__init__()
        self.use_color = use_color
        self._fmt = "[{asctime}] [{levelname:<8}] [{name}] {message}"

    def format(self, record: logging.LogRecord) -> str:
        record.asctime = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = self._fmt.format(
            asctime=record.asctime,
            levelname=record.levelname,
            name=record.name,
            message=record.getMessage(),
        )
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)
        if self.use_color and record.levelname in self.LEVEL_COLORS:
            msg = f"{self.LEVEL_COLORS[record.levelname]}{msg}{self.RESET}"
        return msg


def setup_logger(
    name: str,
    log_dir: str = "./logs",
    level: int = logging.INFO,
    use_json: bool = False,
    max_bytes: int = 10 * 1024 * 1024,   # 10 MB per file
    backup_count: int = 30,               # 30일치 보관
) -> logging.Logger:
    """
    애플리케이션 로거 설정.

    Args:
        name:         로거 이름 (ex: 'youtube_agent')
        log_dir:      로그 파일 저장 디렉토리
        level:        로깅 레벨 (기본: INFO)
        use_json:     True 시 JSON 포맷으로 파일 저장 (Oracle Cloud Logging 연동용)
        max_bytes:    단일 로그 파일 최대 크기 (기본 10 MB)
        backup_count: 보관할 로그 파일 수 (기본 30)

    Returns:
        설정된 logging.Logger 인스턴스
    """
    logger = logging.getLogger(name)

    # 이미 핸들러가 있으면 중복 설정 방지
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # ── 로그 디렉토리 생성 ──
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # ── 1. RotatingFileHandler (파일 로그) ──
    log_filename = os.path.join(log_dir, f"{name}.log")
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    if use_json:
        file_handler.setFormatter(JsonFormatter())
    else:
        file_handler.setFormatter(HumanReadableFormatter(use_color=False))

    # ── 2. StreamHandler (콘솔 / systemd journal) ──
    is_tty = sys.stdout.isatty()
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(HumanReadableFormatter(use_color=is_tty))

    # ── 3. 에러 전용 파일 핸들러 ──
    error_filename = os.path.join(log_dir, f"{name}.error.log")
    error_handler = logging.handlers.RotatingFileHandler(
        filename=error_filename,
        maxBytes=max_bytes,
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(HumanReadableFormatter(use_color=False))

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.addHandler(error_handler)

    logger.info("Logger '%s' initialized. Log dir: %s", name, log_dir)
    return logger


def get_logger(name: str = "youtube_agent") -> logging.Logger:
    """모듈 전역에서 공유하는 로거 인스턴스를 가져온다."""
    return logging.getLogger(name)


# ── 직접 실행 시 동작 확인 ──
if __name__ == "__main__":
    logger = setup_logger(
        name="youtube_agent",
        log_dir="./logs",
        use_json=False,
    )
    logger.debug("DEBUG 메시지 테스트")
    logger.info("INFO 메시지 테스트 - 에이전트 시작")
    logger.warning("WARNING 메시지 테스트")
    logger.error("ERROR 메시지 테스트")
    try:
        raise ValueError("의도적 예외 테스트")
    except ValueError:
        logger.exception("EXCEPTION 테스트 - 스택 트레이스 포함")
    print("\n[OK] Logger initialized. ./logs/ directory confirmed.")
