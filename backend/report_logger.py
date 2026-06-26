from datetime import datetime
from pathlib import Path

from .config import LOGS_DIR, ensure_project_dirs


def log_event(report_id: str, message: str) -> None:
    ensure_project_dirs()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path = LOGS_DIR / f"{report_id}.log"
    line = f"[{timestamp}] {message}"
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    log_path.write_text(existing + line + "\n", encoding="utf-8")
    print(line, flush=True)


def get_log_path(report_id: str) -> Path:
    return LOGS_DIR / f"{report_id}.log"
