from pathlib import Path
import argparse, json, sys, requests, yaml, os, datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box
from rich.prompt import Prompt

from .engine import play, stats
from .profiles import (
    create as profile_create,
    login as profile_login,
    list_profiles,
    current_profile_name,
    load_state,
)
from .sync import sync_default
from .constants import VERSION

console = Console()
PROFILE_CREATED = False


# ---------------------------------------------------------
# Profile Setup
# ---------------------------------------------------------
def ensure_profile():
    global PROFILE_CREATED
    if PROFILE_CREATED:
        return False

    state = load_state()
    player = state.get("player", {})

    if player.get("email") and player.get("gamer"):
        return False

    console.print(Panel.fit("🧠 Let's set up your DevOpsMind profile!", border_style="cyan"))

    name = Prompt.ask("👤 Enter username").strip() or "player"
    gamer = Prompt.ask("🎮 Choose your gamer tag (nickname)").strip() or name
    email = Prompt.ask("📧 Enter your email (for XP sync / recovery)").strip()

    profile_create(name)
    profile_file = Path.home() / ".devopsmind" / "profiles" / f"{name}.yaml"

    if profile_file.exists():
        data = yaml.safe_load(profile_file.read_text())
        data["player"]["gamer"] = gamer
        data["player"]["email"] = email
        profile_file.write_text(yaml.safe_dump(data))

    console.print(Panel.fit(f"✅ Profile '{name}' ({gamer}) created!", border_style="green"))
    PROFILE_CREATED = True
    return True


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------
def show_header():
    st = load_state()
    player = st.get("player", {})
    name = player.get("name", "default")
    email = player.get("email", "")
    xp = player.get("xp", 0)
    rank = player.get("rank", "Beginner")

    console.print("\n╭──────────────────────────╮")
    console.print(f"│ DevOpsMind v{VERSION} Ready! │")
    console.print("╰──────────────────────────╯")
    console.print(f"👤 Profile: {name} ({email})  |  🧠 XP: {xp}  |  🏅 Rank: {rank}\n")


# ---------------------------------------------------------
# Save submission YAML for later sync (kept for compatibility)
# ---------------------------------------------------------
def save_submission(data):
    """
    Save a challenge completion YAML for syncing later.
    (Kept for backward compatibility but no longer used directly after fix.)
    """
    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    pending_dir = Path.home() / ".devopsmind" / ".pending_sync"
    pending_dir.mkdir(parents=True, exist_ok=True)

    name = data.get("username", data.get("gamer", "player"))
    filename = f"{name}_{ts}.yaml"
    yaml_path = pending_dir / filename

    with open(yaml_path, "w") as f:
        yaml.safe_dump(data, f)

    return yaml_path


# ---------------------------------------------------------
# Leaderboard (Safe)
# ---------------------------------------------------------
def cmd_leaderboard():
    show_header()
    console.print(Panel.fit("🏆 Global Leaderboard", border_style="blue"))

    urls = [
        "https://raw.githubusercontent.com/InfraForgeLabs/DevOpsMind/leaderboard/leaderboard/leaderboard.json",
        "https://raw.githubusercontent.com/InfraForgeLabs/DevOpsMind/leaderboard/leaderboard.json",
    ]
    override = os.getenv("DEVOPSMIND_LEADERBOARD_URL")
    if override:
        urls.insert(0, override)

    data = None
    for u in urls:
        try:
            resp = requests.get(u, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                break
        except Exception:
            pass

    if not isinstance(data, dict) or "players" not in data:
        console.print("[yellow]⚠️ Invalid leaderboard format.[/yellow]")
        return

    data = sorted(data["players"], key=lambda x: x.get("xp", 0), reverse=True)

    table = Table(title="🌐 Global Leaderboard", box=box.SIMPLE_HEAVY)
    table.add_column("Rank", justify="center")
    table.add_column("Gamer Tag", style="cyan")
    table.add_column("XP", justify="right", style="green")
    table.add_column("Rank Title", style="magenta")

    for i, entry in enumerate(data, 1):
        gamer = str(entry.get("gamer", "?"))
        xp = str(entry.get("xp", entry.get("score", 0)))
        rank = str(entry.get("rank", "-"))
        table.add_row(str(i), gamer, xp, rank)

    console.print(table)


# ---------------------------------------------------------
# Auto Submit — fully improved
# ---------------------------------------------------------
def auto_submit_via_worker(show_message=True):
    """
    Automatically sync all pending XP submissions to the Cloudflare Worker.
    """
    state = load_state()
    player = state.get("player", {})
    name = player.get("name", "default")

    pending_dir = Path.home() / ".devopsmind" / ".pending_sync"
    pending_dir.mkdir(parents=True, exist_ok=True)

    yaml_files = sorted(pending_dir.glob("*.yaml"))
    if not yaml_files:
        if show_message:
            console.print("✅ No pending submissions to send.")
        return

    WORKER_URL = os.getenv(
        "DEVOPSMIND_WORKER_URL",
        "https://devopsmind-relay.gauravchile05.workers.dev"
    )

    for file in yaml_files:
        try:
            yaml_str = file.read_text()
            resp = requests.post(
                WORKER_URL,
                headers={"Content-Type": "text/plain"},
                data=yaml_str.encode("utf-8"),
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    console.print(
                        f"✅ Submitted {file.name} → {data.get('branch', 'leaderboard')} "
                        f"({data.get('sha256','')[:8]})"
                    )
                    file.unlink(missing_ok=True)
                else:
                    console.print(f"[yellow]⚠️ Worker rejected {file.name}[/yellow]")
            else:
                console.print(f"[yellow]⚠️ Worker HTTP {resp.status_code}[/yellow]")
        except Exception as e:
            console.print(f"[red]🌐 Submission failed for {file.name}: {e}[/red]")


# ---------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------
def main():
    ensure_profile()

    p = argparse.ArgumentParser(prog="devopsmind", description="DevOpsMind — Gamified DevOps Simulator")
    p.add_argument("--stack", help="Filter challenges by stack", default=None)
    sub = p.add_subparsers(dest="cmd", required=False)

    sub.add_parser("list", help="List challenges")
    play_cmd = sub.add_parser("play", help="Play a challenge")
    play_cmd.add_argument("id")
    val_cmd = sub.add_parser("validate", help="Validate a challenge")
    val_cmd.add_argument("id")

    sub.add_parser("stats", help="Show stats")
    sub.add_parser("leaderboard", help="Show global leaderboard")
    sub.add_parser("sync", help="Sync challenges")
    sub.add_parser("doctor", help="Run diagnostics")
    sub.add_parser("submit", help="Force submit to leaderboard")

    args = p.parse_args()
    if len(sys.argv) == 1:
        cmd_list()
        return

    cmd = args.cmd
    if cmd == "leaderboard":
        cmd_leaderboard()
    elif cmd == "play":
        show_header()
        success, _ = play(args.id, {}, return_data=True)
        if success:
            console.print("🧠 XP sync already queued automatically.")
            console.print("\n🏆 Challenge completed successfully! Syncing leaderboard...\n")
            auto_submit_via_worker(show_message=True)
    elif cmd == "validate":
        show_header()
        success, _ = play(args.id, {}, return_data=True)
        if success:
            console.print("🧠 XP sync already queued automatically.")
            console.print("\n🏆 Challenge completed successfully! Syncing leaderboard...\n")
            auto_submit_via_worker(show_message=True)
    elif cmd == "submit":
        show_header()
        console.print("🧠 Manual leaderboard sync...")
        auto_submit_via_worker(show_message=True)
