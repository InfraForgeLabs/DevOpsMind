from pathlib import Path
import argparse, json, sys, requests, yaml, os
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

    if not isinstance(data, list):
        console.print("[yellow]⚠️ Invalid leaderboard format.[/yellow]")
        return

    def safe_xp(entry):
        try:
            return int(entry.get("xp", entry.get("score", 0)) or 0)
        except Exception:
            return 0

    data = sorted([x for x in data if isinstance(x, dict)], key=safe_xp, reverse=True)

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
# Auto Submit — clean, silent by default
# ---------------------------------------------------------
def auto_submit_via_worker(show_message=True):
    state = load_state()
    name = state["player"]["name"]
    pending_dir = Path.home() / ".devopsmind" / ".pending_sync"
    yaml_path = pending_dir / f"{name}.yaml"
    if not yaml_path.exists():
        return

    yaml_str = yaml_path.read_text()
    WORKER_URL = os.getenv(
        "DEVOPSMIND_WORKER_URL",
        "https://devopsmind-relay.gauravchile05.workers.dev"
    )

    try:
        resp = requests.post(
            WORKER_URL,
            headers={"Content-Type": "text/yaml"},
            data=yaml_str.encode("utf-8"),
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                if show_message:
                    console.print(f"✅ Auto-synced leaderboard ({name}) → {data['sha256'][:12]}...")
                yaml_path.unlink(missing_ok=True)
        elif show_message:
            console.print(f"[yellow]⚠️ Relay HTTP {resp.status_code}, will retry later.[/yellow]")
    except Exception as e:
        if show_message:
            console.print(f"[dim]🌐 Auto-sync deferred ({e}).[/dim]")


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
        success = play(args.id, {})
        if success:
            console.print("\n🏆 Challenge completed successfully! Syncing leaderboard...\n")
            auto_submit_via_worker(show_message=False)
    elif cmd == "validate":
        show_header()
        success = play(args.id, {})
        if success:
            console.print("\n🏆 Challenge completed successfully! Syncing leaderboard...\n")
            auto_submit_via_worker(show_message=False)
    elif cmd == "submit":
        show_header()
        console.print("🧠 Manual leaderboard sync...")
        auto_submit_via_worker(show_message=True)
