from pathlib import Path
import yaml
import re
from datetime import datetime, timezone
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
    """Record challenge completion locally and persist profile state."""
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
    progress = state.get("progress", {})

    gamer = player.get("gamer") or player.get("name") or player.get("email", "").split("@")[0]
    email = str(player.get("email", "")).strip()
    xp = int(player.get("xp", 0))
    rank = player.get("rank", "Beginner")
    completed = progress.get("completed", [])

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    safe_gamer = re.sub(r"[^a-zA-Z0-9_-]", "", gamer) or "player"

    # 🧩 Prevent duplicate queueing within the same minute
    recent = list(PENDING_SYNC_DIR.glob(f"{safe_gamer}_*.yaml"))
    if any(timestamp[:16] in f.name for f in recent):
        console.print(f"[dim]⏭️ Already queued recent sync for {safe_gamer}.[/dim]")
        return

    out = {
        "gamer": gamer,
        "username": email or gamer,
        "xp": xp,
        "rank": rank,
        "completed": completed,
        "email": email,
        "timestamp": timestamp,
    }

    try:
        file_name = f"{safe_gamer}_{timestamp.replace(':', '-')}.yaml"
        path = PENDING_SYNC_DIR / file_name
        path.write_text(yaml.safe_dump(out, sort_keys=False))
        console.print(f"[dim]🧠 Queued XP sync: {path.name}[/dim]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Failed to queue sync: {e}[/yellow]")

    # Local GitHub profile mirror (optional, no network requirement)
    sync_profile_to_github(state, quiet=True)
