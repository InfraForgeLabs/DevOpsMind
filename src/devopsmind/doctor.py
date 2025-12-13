import platform, sys, shutil
from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from .constants import DATA_DIR, BUNDLED_CHALLENGES

console = Console()

def run_doctor():
    table = Table(title="🩺 DevOpsMind Doctor", show_header=True)
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")

    py_ok = sys.version_info >= (3, 8)
    table.add_row("Python version ≥ 3.8", "✅" if py_ok else "❌")

    table.add_row("Operating System", platform.system())

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        writable = True
    except Exception:
        writable = False
    table.add_row("Data directory writable", "✅" if writable else "❌")

    table.add_row("Bundled challenges found", "✅" if BUNDLED_CHALLENGES.exists() else "❌")

    git_ok = shutil.which("git") is not None
    table.add_row("git installed", "✅" if git_ok else "⚠️ Optional")

    console.print(table)

    if not py_ok:
        console.print(Panel.fit("[red]Upgrade Python to 3.8+[/red]"))
