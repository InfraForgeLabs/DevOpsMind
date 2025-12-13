#!/usr/bin/env bash
set -e

echo "🧠 DevOpsMind bootstrap starting..."

# --- Check prerequisites ---
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Python3 not found. Please install Python 3.9+."
  exit 1
fi

if ! command -v pip >/dev/null 2>&1; then
  echo "❌ pip not found. Install it with: sudo apt install python3-pip"
  exit 1
fi

DM_HOME="${HOME}/.devopsmind"
VENV="${DM_HOME}/venv"

# --- Create home directories ---
mkdir -p "${DM_HOME}/profiles/default" "${DM_HOME}/challenges" "${DM_HOME}/backups" "${DM_HOME}/logs"

if [ ! -f "${DM_HOME}/current_profile" ]; then
  echo "default" > "${DM_HOME}/current_profile"
fi

echo "📦 Creating Python virtual environment..."
python3 -m venv "${VENV}"

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

echo "📥 Installing Python dependencies..."
pip install --upgrade pip wheel setuptools

REQ_FILE="$(realpath "$(dirname "$0")/../requirements.txt")"
if [ -f "${REQ_FILE}" ]; then
  pip install -r "${REQ_FILE}"
else
  echo "⚠️  requirements.txt not found, skipping."
fi

# --- Ensure Terraform parser dependency (fix for 'No module named hcl2') ---
if ! python3 -c "import hcl2" >/dev/null 2>&1; then
  echo "🧩 Installing missing dependency: python-hcl2"
  pip install python-hcl2
fi

# --- Optional DevOps tools for specific challenge categories ---
echo "🔍 Checking optional tools..."
for tool in ansible docker kubectl helm terraform; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "⚠️  $tool not found (some challenges may not run)."
  fi
done

# --- Install CLI launcher ---
LAUNCHER_DST="${HOME}/.local/bin/devopsmind"
mkdir -p "${HOME}/.local/bin"

cat <<'EOF' > "${LAUNCHER_DST}"
#!/usr/bin/env bash
set -e
DM_HOME="${HOME}/.devopsmind"
VENV="${DM_HOME}/venv"
if [ ! -d "${VENV}" ]; then
  echo "❌ DevOpsMind not bootstrapped. Run: bash scripts/bootstrap.sh"
  exit 1
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
python3 -m devopsmind "$@"
EOF

chmod +x "${LAUNCHER_DST}"

# --- Ensure ~/.local/bin in PATH ---
for SHELL_RC in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
  if [ -f "${SHELL_RC}" ] && ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "${SHELL_RC}" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${SHELL_RC}"
  fi
done

if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "✅ Bootstrap complete."
echo "📂 User data: ${DM_HOME}"
echo "▶️  Try now: devopsmind list"
