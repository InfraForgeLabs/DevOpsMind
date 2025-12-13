from pathlib import Path
import requests, yaml, os, hashlib
from rich.console import Console
from datetime import datetime

console = Console()

WORKER_URL = os.getenv(
    "DEVOPSMIND_WORKER_URL",
    "https://devopsmind-relay.gauravchile05.workers.dev"
)
PENDING_DIR = Path.home() / ".devopsmind" / ".pending_sync"


def submit_pending(show_details=True):
    """Submit all queued YAML files safely (offline-resilient)."""
    if not PENDING_DIR.exists():
        console.print("[yellow]⚠️ No pending sync folder found.[/yellow]")
        return

    files = list(PENDING_DIR.glob("*.yaml"))
    if not files:
        console.print("[green]✅ No pending submissions to send.[/green]")
        return

    console.print("\n╭──────────────────────────────────────────────────╮")
    console.print("│ 🚀 Submitting pending progress to leaderboard... │")
    console.print("╰──────────────────────────────────────────────────╯")

    ok_count = 0
    for f in files:
        try:
            data = f.read_text()
            parsed = yaml.safe_load(data) or {}

            # 🧠 Extract gamer/email for metadata headers
            gamer = parsed.get("gamer") or parsed.get("name") or "unknown"
            email = str(parsed.get("email", "")).strip().lower()
            email_hash = hashlib.sha256(email.encode()).hexdigest() if email else None

            headers = {
                "Content-Type": "text/yaml",
                "X-Gamer": gamer,
                "X-Email-Hash": email_hash or "",
            }

            resp = requests.post(
                WORKER_URL,
                headers=headers,
                data=data.encode("utf-8"),
                timeout=10,
            )

            if resp.status_code == 200:
                try:
                    rj = resp.json()
                except Exception:
                    rj = {}

                if rj.get("ok"):
                    console.print(f"✅ Submitted {f.name} → {rj.get('sha256', '')[:12]}")
                    f.unlink(missing_ok=True)
                    ok_count += 1
                else:
                    console.print(f"[yellow]🌐 Worker error: {rj.get('error', 'Unknown')}, kept for retry.[/yellow]")
            else:
                console.print(f"[yellow]🌐 Worker returned HTTP {resp.status_code}, keeping for retry.[/yellow]")

        except Exception as e:
            console.print(f"[dim]🌐 Network error: {e}[/dim]")

    if ok_count:
        console.print(f"\n[green]✅ Successfully submitted {ok_count} file(s)![/green]\n")
    else:
        console.print("\n[yellow]⚠️ No successful submissions this round.[/yellow]\n")
