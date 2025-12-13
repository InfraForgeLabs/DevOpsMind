from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import yaml, requests, json, hashlib

from .profiles import PROFILES, load_state

console = Console()


# ---------------------------------------------------------
# 🌍 Ensure Cached Global Leaderboard (Smart Auto-Update)
# ---------------------------------------------------------
def ensure_leaderboard_cache(force: bool = False) -> Path | None:
    """
    Ensure ~/.devopsmind/leaderboard/leaderboard.json exists.
    Auto-downloads only if missing or outdated (based on last_updated or SHA256 hash).
    """
    lb_dir = Path.home() / ".devopsmind" / "leaderboard"
    lb_file = lb_dir / "leaderboard.json"
    lb_dir.mkdir(parents=True, exist_ok=True)

    url = "https://raw.githubusercontent.com/InfraForgeLabs/DevOpsMind/leaderboard/leaderboard/leaderboard.json"

    # If cache exists and not forced, compare timestamps or hashes
    if lb_file.exists() and not force:
        try:
            local_data = json.loads(lb_file.read_text())
            local_updated = local_data.get("last_updated", "")

            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                remote_data = json.loads(r.text)
                remote_updated = remote_data.get("last_updated", "")

                # ✅ Compare timestamp first
                if remote_updated == local_updated:
                    console.print("[dim]✅ Leaderboard cache is up-to-date.[/dim]")
                    return lb_file

                # 🧩 Compare hash if timestamps differ
                local_hash = hashlib.sha256(lb_file.read_bytes()).hexdigest()
                remote_hash = hashlib.sha256(r.text.encode()).hexdigest()
                if local_hash == remote_hash:
                    console.print("[dim]✅ Leaderboard cache unchanged (same hash).[/dim]")
                    return lb_file

                # 🔄 Update if different
                lb_file.write_text(r.text, encoding="utf-8")
                console.print("[dim]🔄 Leaderboard updated (remote changes detected).[/dim]")
                return lb_file
            else:
                console.print(f"[yellow]⚠️ Remote fetch failed (HTTP {r.status_code}). Using cached version.[/yellow]")
                return lb_file
        except Exception as e:
            console.print(f"[yellow]⚠️ Cache check failed ({e}), using local version if valid.[/yellow]")
            return lb_file

    # If no cache, fetch fresh
    try:
        console.print("[dim]🌐 Downloading leaderboard.json...[/dim]")
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            lb_file.write_text(r.text, encoding="utf-8")
            console.print("[dim]✅ Cached leaderboard.json locally.[/dim]")
            return lb_file
        else:
            console.print(f"[yellow]⚠️ Could not fetch leaderboard (HTTP {r.status_code}).[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Network error fetching leaderboard: {e}[/yellow]")

    return lb_file if lb_file.exists() else None


# ---------------------------------------------------------
# 🌍 Fetch Global Leaderboard (Cached First)
# ---------------------------------------------------------
def fetch_global_leaderboard() -> list:
    """Load leaderboard.json from cache or fetch fresh if needed."""
    lb_file = ensure_leaderboard_cache()
    if not lb_file or not lb_file.exists():
        return []

    try:
        data = json.loads(lb_file.read_text())
        return data.get("players", [])
    except Exception as e:
        console.print(f"[yellow]⚠️ Invalid leaderboard data ({e}).[/yellow]")
        return []


# ---------------------------------------------------------
# 💻 Local Leaderboard (Profiles Folder)
# ---------------------------------------------------------
def fetch_local_leaderboard() -> list:
    """Read all local profile YAML files for XP and rank."""
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


# ---------------------------------------------------------
# 🏆 Display Leaderboards
# ---------------------------------------------------------
def show_leaderboards():
    """Display both local and global leaderboards with XP & rank info."""
    state = load_state()
    xp = state["player"]["xp"]
    rank = state["player"]["rank"]

    # Summary panel
    console.print(Panel.fit(
        f"🏅 XP: [bold green]{xp}[/bold green]  |  Rank: [bold cyan]{rank}[/bold cyan]",
        border_style="green"
    ))

    # Local leaderboard
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

    # Global leaderboard
    console.print("\n[bold cyan]🌍 Global Leaderboard[/bold cyan]")
    global_data = fetch_global_leaderboard()

    global_table = Table(show_header=True, header_style="bold blue")
    global_table.add_column("Player", justify="left", style="cyan")
    global_table.add_column("XP", justify="right", style="green")
    global_table.add_column("Rank", justify="center", style="yellow")

    if global_data:
        for i, entry in enumerate(global_data[:15], start=1):  # Top 15
            player_name = entry.get("gamer") or entry.get("player") or "Unknown"
            global_table.add_row(
                f"{i}. {player_name}",
                str(entry.get("xp", 0)),
                entry.get("rank", "Beginner")
            )
        console.print(global_table)
    else:
        console.print("[yellow]⚠️ No global leaderboard data available (offline?).[/yellow]")
