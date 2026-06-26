from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"
IMAGES_DIR = PROJECT_ROOT / "outputs" / "images"
DIAGRAMS_DIR = PROJECT_ROOT / "assets" / "diagrams"
LOGS_DIR = PROJECT_ROOT / "logs"
PROFILE_PATH = DATA_DIR / "profile.json"

load_dotenv(PROJECT_ROOT / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

IMAGE_API_BASE_URL = os.getenv("IMAGE_API_BASE_URL", "").rstrip("/")
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY", "").strip()
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-2")
IMAGE_API_TIMEOUT = int(os.getenv("IMAGE_API_TIMEOUT", "300"))
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "768x768")


def ensure_project_dirs() -> None:
    for directory in (DATA_DIR, REPORTS_DIR, IMAGES_DIR, DIAGRAMS_DIR, LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
