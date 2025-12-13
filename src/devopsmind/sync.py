from pathlib import Path
import shutil, json, os, yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from datetime import datetime
from .constants import BUNDLED_CHALLENGES, CHALLENGE_DIR
from .profiles import load_state, save_state

console = Console()

def sync_default():
    """Synchronize local challenge registry and merge pending XP progress."""
    console.print(Panel.fit("🧠 Syncing DevOpsMind Challenges", border_style="cyan"))

    CHALLENGE_DIR.mkdir(parents=True, exist_ok=True)
    pending_dir = Path.home() / ".devopsmind" / ".pending_sync"
    pending_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # 🧩 Merge queued XP & completed challenges first
    # ---------------------------------------------------------
    state = load_state()
    player = state["player"]
    progress = state["progress"]
    merged = False

    pending_files = sorted(pending_dir.glob("*.yaml"))
    if pending_files:
        total_xp = 0
        completed = set(progress.get("completed", []))

        for f in pending_files:
            try:
                data = yaml.safe_load(f.read_text())
                total_xp += int(data.get("xp", 0))
                completed.update(data.get("completed", []))
                f.unlink(missing_ok=True)
            except Exception as e:
                console.print(f"[yellow]⚠️ Skipped invalid sync file {f.name}: {e}[/yellow]")

        if total_xp > 0 or completed:
            player["xp"] = player.get("xp", 0) + total_xp
            progress["completed"] = sorted(list(completed))

            # Simple XP → rank promotion
            rank_thresholds = {
                "Beginner": 0,
                "Explorer": 500,
                "Engineer": 1500,
                "Architect": 3000,
                "Master": 5000,
            }
            for rank, req in reversed(rank_thresholds.items()):
                if player["xp"] >= req:
                    player["rank"] = rank
                    break

            save_state(state)
            merged = True
            console.print(f"✅ Merged {len(pending_files)} pending file(s) → +{total_xp} XP")
    else:
        console.print("[dim]No pending XP updates found.[/dim]")

    # ---------------------------------------------------------
    # 📦 Copy bundled challenges to local directory
    # ---------------------------------------------------------
    new = 0
    updated = 0

    for src in BUNDLED_CHALLENGES.rglob("*"):
        if src.is_dir():
            continue

        rel = src.relative_to(BUNDLED_CHALLENGES)
        dest = CHALLENGE_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        if not dest.exists():
            shutil.copy2(src, dest)
            new += 1
        else:
            if src.stat().st_mtime > dest.stat().st_mtime:
                shutil.copy2(src, dest)
                updated += 1

    # ---------------------------------------------------------
    # 🗂️ Rebuild challenge registry (JSON)
    # ---------------------------------------------------------
    registry = []
    for category in sorted(CHALLENGE_DIR.iterdir()):
        if not category.is_dir():
            continue
        for diff in ["easy", "medium", "hard"]:
            diff_path = category / diff
            if not diff_path.exists():
                continue

            meta_file = diff_path / "meta.json"
            yaml_file = diff_path / "challenge.yaml"

            if meta_file.exists():
                try:
                    registry.append(json.loads(meta_file.read_text()))
                except Exception as e:
                    console.print(f"[yellow]⚠️ Skipped invalid meta.json in {diff_path}: {e}[/yellow]")
            elif yaml_file.exists():
                try:
                    data = yaml.safe_load(yaml_file.read_text())
                    registry.append({
                        "id": data.get("id", f"{category.name}-{diff}"),
                        "title": data.get("title", f"{category.name} ({diff})"),
                        "difficulty": diff,
                        "xp": data.get("xp", 100),
                        "category": category.name
                    })
                except Exception as e:
                    console.print(f"[yellow]⚠️ Skipped invalid challenge.yaml in {diff_path}: {e}[/yellow]")

    registry_path = Path.home() / ".devopsmind" / "challenges.json"
    registry_path.write_text(json.dumps({"challenges": registry}, indent=2))
    console.print(f"🗂️  Indexed {len(registry)} challenges to {registry_path}")

    # ---------------------------------------------------------
    # 📊 Summary Table
    # ---------------------------------------------------------
    table = Table(title="Sync Summary", box=None)
    table.add_column("New", justify="center", style="green")
    table.add_column("Updated", justify="center", style="yellow")
    table.add_row(str(new), str(updated))
    console.print(table)

    if merged:
        s = load_state()
        summary = Table(title="Player Progress", box=None)
        summary.add_column("XP", justify="center")
        summary.add_column("Rank", justify="center")
        summary.add_column("Completed", justify="center")
        summary.add_row(str(s["player"]["xp"]), s["player"]["rank"], str(len(s["progress"]["completed"])))
        console.print(summary)

    console.print(Panel.fit("✅ Sync complete.", border_style="green"))
    console.print("\n💡 Tip:")
    console.print("   👉 Run [cyan]devopsmind play <id>[/cyan] to start a challenge.")
    console.print("   🚀 Use [cyan]devopsmind submit[/cyan] to send your progress to the leaderboard.\n")
