from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import yaml, requests, json

from .profiles import PROFILES, load_state

console = Console()

def ensure_leaderboard_cache(force: bool = False) -> Path | None:
    lb_dir = Path.home() / ".devopsmind" / "leaderboard"
    lb_file = lb_dir / "leaderboard.json"
    lb_dir.mkdir(parents=True, exist_ok=True)
    url = "https://raw.githubusercontent.com/InfraForgeLabs/DevOpsMind/leaderboard/leaderboard/leaderboard.json"

    if lb_file.exists() and not force:
        try:
            local_data = json.loads(lb_file.read_text())
            local_updated = local_data.get("last_updated", "")
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                remote_data = json.loads(r.text)
                if remote_data.get("last_updated", "") == local_updated:
                    console.print("[dim]✅ Leaderboard cache is up-to-date.[/dim]")
                    return lb_file
                lb_file.write_text(r.text, encoding="utf-8")
                console.print("[dim]🔄 Leaderboard updated.[/dim]")
                return lb_file
        except Exception:
            return lb_file

    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            lb_file.write_text(r.text, encoding="utf-8")
            console.print("[dim]✅ Cached leaderboard.json locally.[/dim]")
            return lb_file
    except Exception as e:
        console.print(f"[yellow]⚠️ Network error fetching leaderboard: {e}[/yellow]")

    return lb_file if lb_file.exists() else None


def fetch_global_leaderboard() -> dict:
    lb_file = ensure_leaderboard_cache()
    if not lb_file or not lb_file.exists():
        return {}
    try:
        return json.loads(lb_file.read_text())
    except Exception:
        return {}


def fetch_local_leaderboard() -> list:
    rows = []
    for pf in PROFILES.glob("*.yaml"):
        try:
            data = yaml.safe_load(pf.read_text())
            player = data.get("player", {})
            name = player.get("name", pf.stem)
            gamer = player.get("gamer", "")
            xp = player.get("xp", 0)
            rank = player.get("rank", "Beginner")
            display = f"{name} ({gamer})" if gamer else name
            rows.append((display, xp, rank))
        except Exception:
            pass
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


def show_leaderboards():
    state = load_state()
    xp = state["player"]["xp"]
    rank = state["player"]["rank"]

    console.print(Panel.fit(
        f"🏅 XP: [bold green]{xp}[/bold green]  |  Rank: [bold cyan]{rank}[/bold cyan]",
        border_style="green"
    ))

    console.print("\n[bold cyan]💻 Local Leaderboard[/bold cyan]")
    local_data = fetch_local_leaderboard()
    local_table = Table(show_header=True, header_style="bold magenta")
    local_table.add_column("Player", justify="left", style="cyan")
    local_table.add_column("XP", justify="right", style="green")
    local_table.add_column("Rank", justify="center", style="yellow")

    if local_data:
        for name, xp_val, rk in local_data:
            local_table.add_row(name, str(xp_val), rk)
        console.print(local_table)
    else:
        console.print("[yellow]No local profiles found.[/yellow]")

    console.print("\n[bold cyan]🌍 Global Leaderboard[/bold cyan]")
    data = fetch_global_leaderboard()
    players = data.get("players", [])
    updated = data.get("last_updated", "Unknown")

    global_table = Table(show_header=True, header_style="bold blue")
    global_table.add_column("Rank", justify="right", style="bold")
    global_table.add_column("Player", justify="left", style="cyan")
    global_table.add_column("XP", justify="right", style="green")
    global_table.add_column("Rank Title", justify="center", style="yellow")

    RANK_ICONS = {
        "Beginner": "🥉", "Apprentice": "🧑‍💻", "Operator": "⚙️", "Engineer": "🪛", "Specialist": "🔩",
        "Advanced": "🔥", "Expert": "🧠", "Master": "🦾", "Architect": "🧩", "Grandmaster": "🚀",
        "Legend": "👑", "Mythic": "🧬", "Eternal": "🏆", "Ascendant": "🔱", "Vanguard": "💠",
        "Paragon": "⚡", "Virtuoso": "🪶", "Transcendent": "🕊", "Celestial": "🪐", "Infinite": "💫",
    }

    if players:
        for i, entry in enumerate(players[:15], start=1):
            username = entry.get("username") or entry.get("gamer_tag") or ""
            gamer = entry.get("gamer") or entry.get("player") or "Unknown"
            player_name = f"{gamer} [{username or gamer}]"
            rank_name = entry.get("rank", "Beginner")
            icon = RANK_ICONS.get(rank_name, "")
            global_table.add_row(str(i), player_name, str(entry.get("xp", 0)), f"{icon} {rank_name}")
        console.print(global_table)
        console.print(f"[dim]Last updated: {updated}[/dim]")
    else:
        console.print("[yellow]⚠️ No global leaderboard data available (offline?).[/yellow]")
