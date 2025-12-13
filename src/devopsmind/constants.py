from pathlib import Path
import os

VERSION = "1.0.0"

XP_LEVELS = [
    (0, "🌱 DevOps Trainee"),
    (200, "⚙️ Automation Apprentice"),
    (500, "🐳 Container Specialist"),
    (1000, "☸️ Kubernetes Practitioner"),
    (1500, "🚀 DevOps Architect"),
]

XDG = os.environ.get("XDG_DATA_HOME")
DATA_DIR = Path(XDG) / "devopsmind" if XDG else Path.home() / ".devopsmind"

PROFILE_DIR = DATA_DIR / "profiles"
CHALLENGE_DIR = DATA_DIR / "challenges"
BUNDLED_CHALLENGES = Path(__file__).resolve().parent / "challenges"

LEADERBOARD_FILE = DATA_DIR / "leaderboard.json"
PENDING_SYNC_DIR = DATA_DIR / "pending_sync"   # <- new

PRIMARY_COLOR = "cyan"
SUCCESS_COLOR = "green"
ERROR_COLOR = "red"
