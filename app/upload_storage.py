import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(os.getenv("PROFILE_UPLOAD_DIR", ROOT_DIR / "uploads")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
