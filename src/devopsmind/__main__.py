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
from .submit import submit_pending
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
def show_header(show_banner=True):
    st = load_state()
    player = st.get("player", {})
    name = player.get("name", "default")
    email = player.get("email", "")
    xp = player.get("xp", 0)
    rank = player.get("rank", "Beginner")

    if show_banner:
        console.print("\n╭──────────────────────────╮")
        console.print(f"│ DevOpsMind v{VERSION} Ready! │")
        console.print("╰──────────────────────────╯")

    console.print(f"👤 Profile: {name} ({email})  |  🧠 XP: {xp}  |  🏅 Rank: {rank}\n")


# ---------------------------------------------------------
# List Challenges
# ---------------------------------------------------------
def cmd_list(stack: str | None = None):
    show_header()
    registry_path = Path.home() / ".devopsmind" / "challenges.json"
    if not registry_path.exists():
        console.print("[yellow]⚠️ No registry found. Run:[/yellow] [cyan]devopsmind sync[/cyan]")
        return

    data = json.loads(registry_path.read_text())
    challenges = data.get("challenges", [])

    if stack:
        challenges = [c for c in challenges if c["category"].lower() == stack.lower()]
        if not challenges:
            console.print(f"[red]❌ No challenges found for stack '{stack}'.[/red]")
            return
        _print_stack_table(stack, challenges)
        console.print(f"\nTotal: {len(challenges)} | Profile: {current_profile_name()}")
        return

    categories = {}
    for c in challenges:
        cat = c.get("category", "misc")
        categories.setdefault(cat, []).append(c)

    console.print()
    for i, cat in enumerate(sorted(categories.keys()), 1):
        clean_cat = cat.split("-", 1)[-1] if "-" in cat else cat
        console.print(f"{i:02d}-{clean_cat} Track ({len(categories[cat])} challenges)")
    console.print()
    console.print("💡 Tip:")
    console.print("   👉 Run [cyan]devopsmind --stack docker[/cyan] to explore a specific stack.")
    console.print("   🔄 Run [cyan]devopsmind sync[/cyan] to fetch new challenges.")


def _print_stack_table(cat, items):
    from .profiles import load_state
    state = load_state()
    completed = set(state.get("progress", {}).get("completed", []))

    clean_cat = cat.split("-", 1)[-1] if "-" in cat else cat
    table = Table(title=f"{clean_cat} Track ({len(items)} challenges)", box=box.SIMPLE_HEAVY)
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Diff", justify="center")
    table.add_column("XP", justify="right")
    table.add_column("Status", style="magenta")

    for c in sorted(items, key=lambda x: x["id"]):
        diff = c.get("difficulty", "?").lower()
        diff_icon = {"easy": "🧩 easy", "medium": "⚙️ medium", "hard": "💀 hard"}.get(diff, diff)
        status = "[green]✅ Done[/green]" if c["id"] in completed else "[red]❌ Pending[/red]"
        table.add_row(c["id"], c["title"], diff_icon, str(c["xp"]), status)

    console.print(table)


# ---------------------------------------------------------
# Stats
# ---------------------------------------------------------
def cmd_stats():
    show_header()
    s = stats()
    table = Table(title="🏆 Player Stats", box=box.ROUNDED)
    table.add_column("XP", justify="center")
    table.add_column("Rank", justify="center")
    table.add_column("Completed", justify="center")
    table.add_row(str(s["xp"]), s["rank"], str(s["completed_count"]))
    console.print(table)


# ---------------------------------------------------------
# Hints & Descriptions
# ---------------------------------------------------------
def cmd_hint(ch_id: str):
    from .engine import discover
    show_header()
    challenges = discover()
    ch = next((c for c in challenges if c.id == ch_id), None)
    if not ch:
        console.print(f"[red]❌ Challenge not found: {ch_id}[/red]")
        return
    console.print(Panel.fit(ch.hint or "No hint provided.", border_style="cyan"))


def cmd_describe(ch_id: str):
    from .engine import discover
    show_header(show_banner=False)
    challenges = discover()
    ch = next((c for c in challenges if c.id == ch_id), None)
    if not ch:
        console.print(f"[red]❌ Challenge not found: {ch_id}[/red]")
        return

    workspace = Path.home() / "DevOpsMind" / "workspace" / ch.id
    meta_panel = Panel.fit(
        f"🧩 [bold cyan]Challenge:[/bold cyan] {ch.id}\n"
        f"📦 [bold yellow]Difficulty:[/bold yellow] {getattr(ch, 'difficulty', 'unknown')} "
        f"| 🧠 [bold green]XP:[/bold green] {getattr(ch, 'xp', '?')}\n"
        f"📂 [bold blue]Workspace:[/bold blue] {workspace}",
        border_style="blue",
    )
    console.print(meta_panel)

    possible_dirs = [ch.path]
    base_dir = Path.home() / ".devopsmind" / "challenges"
    for root, dirs, files in os.walk(base_dir):
        if ch_id in root:
            possible_dirs.append(Path(root))

    for d in possible_dirs:
        for candidate in ["description.md", "DESCRIPTION.md", "README.md"]:
            desc_file = d / candidate
            if desc_file.exists():
                text = desc_file.read_text(encoding="utf-8").strip()
                console.print(Panel(Markdown(text), border_style="cyan"))
                return

    console.print(f"[yellow]⚠️ No description file found for {ch_id}.[/yellow]")


# ---------------------------------------------------------
# Leaderboard (Fixed + Robust)
# ---------------------------------------------------------
def cmd_leaderboard():
    show_header()
    console.print(Panel.fit("🏆 Global Leaderboard", border_style="blue"))

    urls = [
        "https://raw.githubusercontent.com/InfraForgeLabs/DevOpsMind/leaderboard/leaderboard.json",
        "https://raw.githubusercontent.com/InfraForgeLabs/DevOpsMind/leaderboard/leaderboard/leaderboard.json",
    ]
    override = os.getenv("DEVOPSMIND_LEADERBOARD_URL")
    if override:
        urls.insert(0, override)

    data = None
    used_url = None

    for u in urls:
        try:
            resp = requests.get(u, timeout=10)
            if resp.status_code == 200:
                parsed = resp.json()
                if isinstance(parsed, dict) and "players" in parsed:
                    data = parsed["players"]
                elif isinstance(parsed, list):
                    data = parsed
                if data:
                    used_url = u
                    break
        except Exception:
            continue

    if not isinstance(data, list) or not data:
        console.print("[yellow]⚠️ Could not load leaderboard data (network/cache issue).[/yellow]")
        console.print("[dim]Try again in a few seconds or check your connection.[/dim]")
        return

    console.print(f"[dim]📡 Loaded leaderboard from {used_url}[/dim]\n")

    data = [x for x in data if isinstance(x, dict)]

    def safe_xp(entry):
        try:
            return int(entry.get("xp", entry.get("score", 0)) or 0)
        except Exception:
            return 0

    data = sorted(data, key=safe_xp, reverse=True)

    table = Table(title="🌐 Global Leaderboard", box=box.SIMPLE_HEAVY)
    table.add_column("Rank", justify="center")
    table.add_column("Gamer Tag", style="cyan")
    table.add_column("XP", justify="right", style="green")
    table.add_column("Rank Title", style="magenta")

    for i, entry in enumerate(data, 1):
        table.add_row(
            str(i),
            str(entry.get("gamer", "?")),
            str(entry.get("xp", entry.get("score", 0))),
            str(entry.get("rank", "-")),
        )

    console.print(table)


# ---------------------------------------------------------
# Main Entrypoint
# ---------------------------------------------------------
def main():
    ensure_profile()
    parser = argparse.ArgumentParser(prog="devopsmind", description="DevOpsMind — Gamified DevOps Simulator")
    parser.add_argument("--stack", help="Filter challenges by stack", default=None)
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("list", help="List challenges")
    play_cmd = sub.add_parser("play", help="Play a challenge")
    play_cmd.add_argument("id")

    val_cmd = sub.add_parser("validate", help="Validate a challenge")
    val_cmd.add_argument("id")
    val_cmd.add_argument("--context", default="{}")

    sub.add_parser("stats", help="Show player stats")
    sub.add_parser("leaderboard", help="Show leaderboard")
    sub.add_parser("sync", help="Sync challenges")
    sub.add_parser("submit", help="Submit pending progress to leaderboard")
    sub.add_parser("doctor", help="Run diagnostics")

    hint = sub.add_parser("hint", help="Show challenge hint")
    hint.add_argument("id")
    desc = sub.add_parser("describe", help="Show challenge description")
    desc.add_argument("id")

    prof = sub.add_parser("profile", help="Manage profiles")
    prof_sub = prof.add_subparsers(dest="pcmd", required=False)
    pc = prof_sub.add_parser("create", help="Create profile")
    pc.add_argument("name")
    pl = prof_sub.add_parser("login", help="Login profile")
    pl.add_argument("name")
    prof_sub.add_parser("list", help="List profiles")

    args = parser.parse_args()
    if len(sys.argv) == 1:
        cmd_list()
        return
    if args.stack and not args.cmd:
        cmd_list(args.stack)
        return

    cmd = args.cmd
    if cmd == "list":
        cmd_list(args.stack)
    elif cmd == "play":
        show_header()
        success = play(args.id, {})
        if success:
            console.print("\n🏆 Challenge completed successfully! Syncing leaderboard...\n")
            submit_pending()
    elif cmd == "validate":
        show_header()
        success = play(args.id, json.loads(args.context))
        if success:
            console.print("\n🏆 Challenge completed successfully! Syncing leaderboard...\n")
            submit_pending()
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "leaderboard":
        cmd_leaderboard()
    elif cmd == "sync":
        show_header()
        sync_default()
    elif cmd == "submit":
        show_header()
        submit_pending()
    elif cmd == "doctor":
        show_header()
        from .doctor import run_doctor
        run_doctor()
    elif cmd == "hint":
        cmd_hint(args.id)
    elif cmd == "describe":
        cmd_describe(args.id)
    elif cmd == "profile":
        show_header()
        if args.pcmd == "create":
            profile_create(args.name)
        elif args.pcmd == "login":
            profile_login(args.name)
        elif args.pcmd == "list":
            list_profiles()
