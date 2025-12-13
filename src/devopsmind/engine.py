from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import importlib.util, yaml, inspect, os, json, shutil
from datetime import datetime
from typing import Dict, Any, List
from .profiles import load_state
from .progress import record_completion, _queue_for_sync  # ✅ sync support


# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLED = REPO_ROOT / "challenges"
HOME = Path.home() / ".devopsmind" / "challenges"
CONFIG_HOME = Path.home() / ".config" / "devopsmind" / "challenges"


# ---------------------------------------------------------
# Unified Output
# ---------------------------------------------------------
def print_success(ch, workspace_dir):
    print("🏅 Challenge completed successfully!")
    print(f"📦 XP Earned: {ch.xp}")
    print(f"🧠 Difficulty: {ch.difficulty}")
    print(f"📂 Workspace: {workspace_dir}")


def print_failure(msg, ch_id, workspace_dir):
    box_width = max(50, len(msg) + 4)
    print("╭" + "─" * box_width + "╮")
    print(f"│ ❌ {msg.ljust(box_width - 2)}│")
    print("╰" + "─" * box_width + "╯")
    print(f"📂 Workspace: {workspace_dir}")
    print(f"💡 Tip: Run \"devopsmind describe {ch_id}\" to view requirements.\n")


# ---------------------------------------------------------
# Challenge Dataclass
# ---------------------------------------------------------
@dataclass
class Challenge:
    id: str
    title: str
    difficulty: str
    xp: int
    tags: list[str]
    path: Path
    hint: str


# ---------------------------------------------------------
# Challenge Discovery
# ---------------------------------------------------------
def _iter_challenge_dirs(base: Path):
    if not base.exists():
        return
    for stack in sorted(base.iterdir()):
        if not stack.is_dir():
            continue
        for tier in ["easy", "medium", "hard"]:
            d = stack / tier
            if (d / "challenge.yaml").exists() or (d / "metadata.json").exists():
                yield d


def discover() -> List[Challenge]:
    found = []
    xp_defaults = {"easy": 50, "medium": 100, "hard": 150}

    for base in [BUNDLED, HOME, CONFIG_HOME]:
        if not base.exists():
            continue

        for d in _iter_challenge_dirs(base):
            meta_file = d / "challenge.yaml"
            if not meta_file.exists():
                meta_file = d / "metadata.json"
            if not meta_file.exists():
                continue

            try:
                if meta_file.suffix == ".yaml":
                    meta = yaml.safe_load(meta_file.read_text())
                else:
                    meta = json.loads(meta_file.read_text())
            except Exception as e:
                print(f"⚠️ Failed to parse metadata in {meta_file}: {e}")
                continue

            diff = meta.get("difficulty", meta.get("diff", "easy")).lower()
            xp_value = meta.get("xp", xp_defaults.get(diff, 50))

            found.append(
                Challenge(
                    id=str(meta.get("id", d.name)),
                    title=meta.get("title", meta.get("id", d.name)),
                    difficulty=diff,
                    xp=int(xp_value),
                    tags=meta.get("tags", []),
                    path=d,
                    hint=meta.get("hint", "No hint provided."),
                )
            )

    uniq = {c.id: c for c in found}
    return sorted(uniq.values(), key=lambda c: c.id.lower())


# ---------------------------------------------------------
# Validator Loader
# ---------------------------------------------------------
def _load_validator(ch_dir: Path):
    v = ch_dir / "validator.py"
    if not v.exists():
        return None
    spec = importlib.util.spec_from_file_location("validator", v)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod if hasattr(mod, "validate") else None


# ---------------------------------------------------------
# Session Log
# ---------------------------------------------------------
def _log_session(ch_id: str, msg: str, success: bool, xp: int):
    logs_dir = Path.home() / "DevOpsMind" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "session.log"

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "✅ SUCCESS" if success else "❌ FAIL"
    xp_str = f" (+{xp} XP)" if success else ""
    line = f"[{ts}] {ch_id} → {status}{xp_str} — {msg}\n"

    try:
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        print(f"⚠️ Failed to write log: {e}")


# ---------------------------------------------------------
# Recursive Challenge Copier (preserves user files)
# ---------------------------------------------------------
def copy_challenge_recursive(src: Path, dest: Path) -> int:
    """
    Recursively copy all valid files/folders (scripts/, logs/, templates/, etc.)
    while skipping __pycache__, hidden system dirs, and preserving user content.
    """
    copied = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", ".pytest_cache"} and not d.startswith(".")]
        rel_path = Path(root).relative_to(src)
        target_dir = dest / rel_path
        target_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            if f.endswith((".pyc", ".pyo", ".DS_Store", ".gitkeep")) or f.startswith("."):
                continue
            src_file = Path(root) / f
            dest_file = target_dir / f
            try:
                shutil.copy2(src_file, dest_file)
                copied += 1
            except Exception as e:
                print(f"⚠️ Failed to copy {src_file}: {e}")
    return copied


# ---------------------------------------------------------
# Play Logic (refresh only challenge files)
# ---------------------------------------------------------
def play(ch_id: str, context: Dict[str, Any] | None = None):
    ch_id = str(ch_id).strip()
    ch = next((c for c in discover() if c.id == ch_id), None)
    if not ch:
        _log_session(ch_id, "Challenge not found.", False, 0)
        return False

    mod = _load_validator(ch.path)
    if not mod:
        _log_session(ch_id, "Validator missing.", False, 0)
        return False

    workspace_root = Path.home() / "DevOpsMind" / "workspace"
    workspace_dir = workspace_root / ch.id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    print(f"📂 Workspace: {workspace_dir}")

    base = Path.home() / ".devopsmind" / "challenges"
    challenge_src = None

    # 🔍 Locate challenge source
    for path in base.rglob("*"):
        if path.is_dir() and path.name.strip().lower() == ch.id.strip().lower():
            challenge_src = path
            break

    if not challenge_src:
        for path in base.rglob("*"):
            if path.is_dir() and path.name.lower() == ch.difficulty.lower() and ch_id.startswith(path.parent.name.split("-")[-1]):
                challenge_src = path
                break

    if not challenge_src and ch.path.exists():
        challenge_src = ch.path

    # 🧹 Smart refresh — preserve user-created files
    if challenge_src and challenge_src.exists():
        challenge_files = {
            str(f.relative_to(challenge_src))
            for f in challenge_src.rglob("*")
            if f.is_file()
        }

        for existing in workspace_dir.rglob("*"):
            rel = existing.relative_to(workspace_dir)
            if existing.name.startswith("."):
                continue
            if str(rel) in challenge_files:
                try:
                    if existing.is_dir():
                        shutil.rmtree(existing)
                    else:
                        existing.unlink()
                except Exception as e:
                    print(f"⚠️ Failed to remove old file {existing}: {e}")

        copied = copy_challenge_recursive(challenge_src, workspace_dir)
        print(f"✅ Copied {copied} file(s) from {challenge_src}.")
    else:
        print(f"⚠️ Could not locate challenge '{ch.id}' in ~/.devopsmind/challenges/.")

    # Run validator
    old_cwd = Path.cwd()
    try:
        os.chdir(workspace_dir)
        sig = inspect.signature(mod.validate)
        ok, msg = (mod.validate() if len(sig.parameters) == 0 else mod.validate(context or {}))
    except Exception as e:
        ok, msg = False, f"Validator threw an exception: {e}"
    finally:
        os.chdir(old_cwd)

    _log_session(ch.id, msg, ok, ch.xp if ok else 0)

    if ok:
        record_completion(ch.id, ch.xp)
        _queue_for_sync(load_state())
        print_success(ch, workspace_dir)
        return True
    else:
        print_failure(msg, ch.id, workspace_dir)
        return False


# ---------------------------------------------------------
# Stats
# ---------------------------------------------------------
def stats() -> dict:
    st = load_state()
    completed = st["progress"]["completed"]
    return {
        "xp": st["player"]["xp"],
        "rank": st["player"]["rank"],
        "badges": st["player"].get("badges", []),
        "completed": completed,
        "completed_count": len(completed),
    }
