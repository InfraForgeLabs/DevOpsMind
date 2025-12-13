from pathlib import Path
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def load_registry():
    """Load challenges from the local registry file (~/.devopsmind/challenges.json)."""
    registry_path = Path.home() / ".devopsmind" / "challenges.json"
    if not registry_path.exists():
        console.print("[yellow]⚠️  No registry found. Try running:[/yellow] [cyan]devopsmind sync[/cyan]")
        return []
    try:
        with open(registry_path) as f:
            data = json.load(f)
        return data.get("challenges", [])
    except Exception as e:
        console.print(f"[red]❌ Failed to load registry:[/red] {e}")
        return []

def list_challenges():
    """Display all available challenges."""
    challenges = load_registry()
    console.print(Panel.fit(" Available Challenges 🎯 ", border_style="cyan"))

    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("ID", style="bold cyan")
    table.add_column("Title")
    table.add_column("Diff", justify="center")
    table.add_column("XP", justify="right")

    if not challenges:
        table.add_row("-", "No challenges found", "-", "-")
    else:
        for c in challenges:
            table.add_row(
                c.get("id", "?"),
                c.get("title", "Unknown"),
                c.get("difficulty", "?").capitalize(),
                str(c.get("xp", "?")),
            )

    console.print(table)
    console.print(f"Total: {len(challenges)} | Profile: default")
