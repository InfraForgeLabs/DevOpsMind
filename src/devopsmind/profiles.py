from pathlib import Path
import yaml, requests, json, os, hashlib
from datetime import datetime
from rich.console import Console
from rich.panel import Panel

console = Console()

# ---------------------------------------------------------
# Paths and Initialization
# ---------------------------------------------------------
BASE_DIR = Path.home() / ".devopsmind"
PROFILES = BASE_DIR / "profiles"
PROFILES.mkdir(parents=True, exist_ok=True)

ACTIVE_PROFILE = PROFILES / "active.txt"
PROFILES_FILE = PROFILES / "default.yaml"

# All wins are queued locally until submit
PENDING_SYNC_DIR = BASE_DIR / ".pending_sync"
PENDING_SYNC_DIR.mkdir(parents=True, exist_ok=True)

# Track last saved state to prevent redundant syncs
_last_saved_state = {}


# ---------------------------------------------------------
# Default Profile Handling
# ---------------------------------------------------------
def _ensure_default_profile():
    """Ensure at least one default profile exists and is valid."""
    default_data = {
        "player": {"name": "default", "gamer": "", "email": "", "xp": 0, "rank": "Beginner"},
        "progress": {"completed": []},
    }

    if not PROFILES_FILE.exists():
        PROFILES_FILE.write_text(yaml.safe_dump(default_data))
        if not ACTIVE_PROFILE.exists():
            ACTIVE_PROFILE.write_text("default")
        return

    # Recover from corruption
    try:
        yaml.safe_load(PROFILES_FILE.read_text())
    except Exception:
        console.print("[yellow]⚠️ Default profile corrupted. Rebuilding...[/yellow]")
        PROFILES_FILE.write_text(yaml.safe_dump(default_data))


# ---------------------------------------------------------
# Load / Save State
# ---------------------------------------------------------
def load_state():
    """Load active profile state, ensuring defaults exist."""
    _ensure_default_profile()

    try:
        active_name = ACTIVE_PROFILE.read_text().strip()
    except FileNotFoundError:
        active_name = "default"
        ACTIVE_PROFILE.write_text(active_name)

    profile_file = PROFILES / f"{active_name}.yaml"
    if not profile_file.exists():
        _ensure_default_profile()
        profile_file = PROFILES_FILE

    try:
        data = yaml.safe_load(profile_file.read_text()) or {}
    except Exception:
        console.print(f"[yellow]⚠️ Profile '{active_name}' is corrupted. Restoring defaults.[/yellow]")
        _ensure_default_profile()
        data = yaml.safe_load(PROFILES_FILE.read_text())

    return data


def save_state(state):
    """Persist profile state and queue for local sync."""
    global _last_saved_state
    _ensure_default_profile()

    # Avoid redundant writes
    if state == _last_saved_state:
        return
    _last_saved_state = state.copy()

    try:
        active_name = ACTIVE_PROFILE.read_text().strip()
    except FileNotFoundError:
        active_name = "default"
        ACTIVE_PROFILE.write_text(active_name)

    profile_file = PROFILES / f"{active_name}.yaml"
    profile_file.write_text(yaml.safe_dump(state))

    # Queue local sync file (but don’t push online yet)
    sync_profile_to_github(state, quiet=True)


# ---------------------------------------------------------
# 🌐 Global Leaderboard Sync (Recovery)
# ---------------------------------------------------------
def sync_profile_from_github(email: str):
    """Fetch XP and progress from global leaderboard using SHA256(email) hash."""
    if not email:
        return None

    url = "https://raw.githubusercontent.com/InfraForgeLabs/DevOpsMind/leaderboard/leaderboard/leaderboard.json"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            console.print(f"[yellow]⚠️ Could not fetch leaderboard (HTTP {r.status_code}).[/yellow]")
            return None
        try:
            leaderboard = r.json()
        except json.JSONDecodeError:
            console.print("[yellow]⚠️ Malformed leaderboard JSON.[/yellow]")
            return None
    except Exception as e:
        console.print(f"[yellow]⚠️ Network issue while fetching leaderboard: {e}[/yellow]")
        return None

    # 🔒 Compute SHA256 hash of email for lookup
    email_hash = hashlib.sha256(email.strip().lower().encode()).hexdigest()

    # Some JSONs may be {"players": [...]} or direct list
    players = leaderboard.get("players", leaderboard)
    if not isinstance(players, list):
        console.print("[yellow]⚠️ Invalid leaderboard structure.[/yellow]")
        return None

    for entry in players:
        if not isinstance(entry, dict):
            continue
        if entry.get("email_hash") == email_hash:
            return entry

    return None


# ---------------------------------------------------------
# ☁️ Queue Local Profile for GitHub Sync
# ---------------------------------------------------------
def sync_profile_to_github(state: dict, quiet: bool = False):
    """
    Queue profile for leaderboard sync (offline-first).
    Creates YAML snapshot in ~/.devopsmind/.pending_sync/
    """
    player = state.get("player", {})
    name = player.get("name", "unknown")
    gamer = player.get("gamer", "")
    email = player.get("email", "")
    xp = player.get("xp", 0)
    rank = player.get("rank", "Beginner")
    completed = state.get("progress", {}).get("completed", [])

    # Append timestamped snapshot — allows multiple offline wins
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = name.replace(" ", "_").replace("/", "_")
    out = {
        "name": name,
        "gamer": gamer,
        "email": email,
        "xp": xp,
        "rank": rank,
        "completed": completed,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        path = PENDING_SYNC_DIR / f"{safe_name}_{timestamp}.yaml"
        path.write_text(yaml.safe_dump(out))
        if not quiet and os.getenv("DEVOPSMIND_VERBOSE_SYNC", "0") == "1":
            console.print(f"[dim]🧠 Queued leaderboard sync: {path.name}[/dim]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Failed to queue leaderboard sync: {e}[/yellow]")


# ---------------------------------------------------------
# Profile Commands
# ---------------------------------------------------------
def create(name: str):
    """Create new profile, restoring XP if found on leaderboard."""
    profile_file = PROFILES / f"{name}.yaml"
    if profile_file.exists():
        console.print(Panel.fit(f"⚠️ Profile '{name}' already exists.", border_style="yellow"))
        return

    gamer = console.input("[bold cyan]🎮 Enter your gamer tag:[/bold cyan] ").strip() or "player"
    email = console.input("[bold cyan]📧 Enter your email (for XP sync/recovery):[/bold cyan] ").strip()

    recovered = sync_profile_from_github(email) if email else None
    if recovered:
        console.print(Panel.fit("☁️ Found existing data on global leaderboard! Restoring XP & rank...", border_style="cyan"))
        data = {
            "player": {
                "name": name,
                "gamer": gamer,
                "email": email,
                "xp": recovered.get("xp", 0),
                "rank": recovered.get("rank", "Beginner"),
            },
            "progress": {"completed": recovered.get("completed", [])},
        }
    else:
        data = {
            "player": {"name": name, "gamer": gamer, "email": email, "xp": 0, "rank": "Beginner"},
            "progress": {"completed": []},
        }

    profile_file.write_text(yaml.safe_dump(data))
    ACTIVE_PROFILE.write_text(name)
    console.print(Panel.fit(f"✅ Profile '{name}' ({gamer}) created!", border_style="green"))

    # Queue once quietly
    sync_profile_to_github(data, quiet=True)


def login(name: str):
    """Switch active profile and refresh XP from leaderboard."""
    profile_file = PROFILES / f"{name}.yaml"
    if not profile_file.exists():
        console.print(Panel.fit(f"❌ Profile '{name}' not found.", border_style="red"))
        return

    data = yaml.safe_load(profile_file.read_text()) or {}
    email = data.get("player", {}).get("email", "")

    recovered = sync_profile_from_github(email) if email else None
    if recovered:
        console.print(Panel.fit("☁️ Synced XP & rank from global leaderboard!", border_style="cyan"))
        data["player"]["xp"] = recovered.get("xp", data["player"].get("xp", 0))
        data["player"]["rank"] = recovered.get("rank", data["player"].get("rank", "Beginner"))
        data["progress"]["completed"] = recovered.get("completed", data.get("progress", {}).get("completed", []))
        profile_file.write_text(yaml.safe_dump(data))
        sync_profile_to_github(data, quiet=True)

    ACTIVE_PROFILE.write_text(name)
    console.print(Panel.fit(f"👤 Switched to profile: {name}", border_style="cyan"))


def list_profiles():
    """List available profiles and highlight the active one."""
    _ensure_default_profile()
    active = ACTIVE_PROFILE.read_text().strip()
    console.print("[bold cyan]Available Profiles:[/bold cyan]")

    profiles = sorted(PROFILES.glob("*.yaml"))
    for f in profiles:
        if f.name.startswith("."):
            continue
        mark = "⭐" if f.stem == active else " "
        console.print(f" {mark} {f.stem}")


def current_profile_name() -> str:
    """Return the active profile name."""
    _ensure_default_profile()
    try:
        return ACTIVE_PROFILE.read_text().strip()
    except FileNotFoundError:
        return "default"
