import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
DATA_DIR = Path(os.environ.get("OPTIMIZARR_DATA_DIR", REPO_ROOT / "data"))
CONFIG_PATH = DATA_DIR / "config.json"
CSV_DIR = DATA_DIR / "csv"
OPTIMIZE_HISTORY_PATH = DATA_DIR / "optimize_history.jsonl"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

ANALYZE_SCRIPT = SCRIPTS_DIR / "analyze-video-bloat.py"
TRANSCODE_SCRIPT = SCRIPTS_DIR / "transcode-1080p-hevc.sh"
SAMPLE_SCRIPT = SCRIPTS_DIR / "sample-test.sh"
