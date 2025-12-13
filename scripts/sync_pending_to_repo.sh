#!/usr/bin/env bash
set -e

# 🧠 DevOpsMind pending sync uploader
# Copies local pending YAMLs into repo and pushes to main.

REPO_DIR="$HOME/DevOpsMind"         # path to your repo clone
LOCAL_PENDING="$HOME/.devopsmind/.pending_sync"
REMOTE_PENDING="$REPO_DIR/.pending_sync"

echo "🧩 Syncing pending leaderboard entries..."

# Make sure repo exists
if [ ! -d "$REPO_DIR/.git" ]; then
  echo "❌ Repo not found at $REPO_DIR"
  exit 1
fi

cd "$REPO_DIR"

# Ensure .pending_sync exists
mkdir -p "$REMOTE_PENDING"

# Copy all pending YAMLs into the repo
if [ -d "$LOCAL_PENDING" ] && ls "$LOCAL_PENDING"/*.yaml >/dev/null 2>&1; then
  cp "$LOCAL_PENDING"/*.yaml "$REMOTE_PENDING"/
  echo "✅ Copied new entries:"
  ls "$REMOTE_PENDING"/*.yaml
else
  echo "⚠️  No new pending YAMLs found."
  exit 0
fi

# Stage and push to main
git checkout main
git pull origin main
git add .pending_sync/*.yaml || true
if git diff --cached --quiet; then
  echo "✅ No new changes to push."
else
  git commit -m "sync: push pending leaderboard updates"
  git push origin main
  echo "🚀 Pending updates pushed to GitHub (main branch)."
fi
