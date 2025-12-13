from pathlib import Path
import yaml
import re
from datetime import datetime
from .profiles import load_state, save_state, sync_profile_to_github
from rich.console import Console

console = Console()

# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------
PENDING_SYNC_DIR = Path.home() / ".devopsmind" / ".pending_sync"
PENDING_SYNC_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Record Completion
# ---------------------------------------------------------
def record_completion(ch_id: str, xp: int):
    """Record completion locally and persist to profile."""
    state = load_state()
    player = state["player"]
    progress = state["progress"]

    if ch_id not in progress.get("completed", []):
        progress.setdefault("completed", []).append(ch_id)
        player["xp"] = player.get("xp", 0) + xp
        console.print(f"[dim]🧠 Recorded completion of '{ch_id}' (+{xp} XP).[/dim]")
        save_state(state)
        _queue_for_sync(state)
    else:
        console.print(f"[dim]🧠 Challenge '{ch_id}' already completed.[/dim]")


# ---------------------------------------------------------
# Queue for Sync (Offline-First)
# ---------------------------------------------------------
def _queue_for_sync(state: dict):
    """
    Queue local profile snapshot for leaderboard sync (offline-first).
    Writes YAML to ~/.devopsmind/.pending_sync/
    """
    player = state.get("player", {})
    name = player.get("name", "unknown")
    gamer = player.get("gamer") or player.get("name") or player.get("email", "").split("@")[0]
    email = player.get("email", "")
    xp = player.get("xp", 0)
    rank = player.get("rank", "Beginner")
    completed = state.get("progress", {}).get("completed", [])

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # ✅ Safe, readable filenames using gamer tag if available
    safe_gamer = re.sub(r"[^a-zA-Z0-9_-]", "", gamer)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    prefix = safe_gamer or safe_name or "player"

    out = {
        "gamer": gamer,
        "name": name,
        "email": email,
        "xp": xp,
        "rank": rank,
        "completed": completed,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        path = PENDING_SYNC_DIR / f"{prefix}_{timestamp}.yaml"
        path.write_text(yaml.safe_dump(out))
        console.print(f"[dim]🧠 Queued XP sync: {path.name}[/dim]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Failed to queue sync: {e}[/yellow]")

    # Also queue for GitHub relay (non-networked)
    sync_profile_to_github(state, quiet=True)
