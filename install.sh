#!/usr/bin/env bash
# =============================================================================
#  AI PC Suitability Checker — Installer
#  Works on: Linux, macOS, Windows (Git Bash / WSL)
# =============================================================================
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}  [INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}  [ OK ]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}  [WARN]${RESET}  $*"; }
error()   { echo -e "${RED}  [ERR ]${RESET}  $*"; exit 1; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║       AI PC SUITABILITY CHECKER — INSTALLER         ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Detect OS ─────────────────────────────────────────────────────────────────
OS="unknown"
case "$(uname -s)" in
  Linux*)   OS="linux"  ;;
  Darwin*)  OS="macos"  ;;
  CYGWIN*)  OS="windows_cygwin" ;;
  MINGW*)   OS="windows_gitbash" ;;
  MSYS*)    OS="windows_msys"   ;;
esac
info "Detected OS: $OS"

# ── Check Python ──────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python python3.11 python3.10 python3.9; do
  if command -v "$cmd" &>/dev/null; then
    VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    MAJOR=$(echo "$VER" | cut -d. -f1)
    MINOR=$(echo "$VER" | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
      PYTHON="$cmd"
      success "Found Python $VER at: $(command -v $cmd)"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  error "Python 3.9+ not found. Please install it:
         Linux:  sudo apt install python3 python3-pip  (Ubuntu/Debian)
                 sudo dnf install python3              (Fedora/RHEL)
         macOS:  brew install python3                  (Homebrew)
         Windows: https://www.python.org/downloads/
         Then re-run this script."
fi

# ── Check pip ─────────────────────────────────────────────────────────────────
if ! "$PYTHON" -m pip --version &>/dev/null; then
  warn "pip not found. Attempting to install..."
  if [[ "$OS" == "linux" ]]; then
    sudo apt-get install -y python3-pip 2>/dev/null || \
    sudo dnf install -y python3-pip 2>/dev/null || \
    "$PYTHON" -m ensurepip --upgrade || error "Could not install pip."
  else
    "$PYTHON" -m ensurepip --upgrade || error "pip unavailable. Install manually."
  fi
fi
success "pip available: $($PYTHON -m pip --version)"

# ── Check/create virtual environment (optional but recommended) ───────────────
VENV_DIR="$(dirname "$0")/.venv"
USE_VENV=false

if [ "${1:-}" = "--no-venv" ]; then
  info "Skipping venv (--no-venv flag)"
else
  if "$PYTHON" -m venv --help &>/dev/null; then
    if [ ! -d "$VENV_DIR" ]; then
      info "Creating virtual environment at .venv/ ..."
      "$PYTHON" -m venv "$VENV_DIR"
      success "Virtual environment created"
    else
      info "Virtual environment already exists at .venv/"
    fi
    USE_VENV=true
    # Activate
    if [[ "$OS" == windows* ]]; then
      PYTHON="$VENV_DIR/Scripts/python"
      PIP="$VENV_DIR/Scripts/pip"
    else
      PYTHON="$VENV_DIR/bin/python"
      PIP="$VENV_DIR/bin/pip"
    fi
  else
    warn "venv module not available — installing system-wide"
  fi
fi

PIP="${PIP:-$PYTHON -m pip}"

# ── Upgrade pip itself ────────────────────────────────────────────────────────
info "Upgrading pip..."
$PYTHON -m pip install --upgrade pip -q
success "pip upgraded"

# ── Install requirements ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REQ_FILE="$SCRIPT_DIR/requirements.txt"

if [ -f "$REQ_FILE" ]; then
  info "Installing from requirements.txt ..."
  $PYTHON -m pip install -r "$REQ_FILE" -q
  success "All packages installed from requirements.txt"
else
  info "Installing packages directly..."
  $PYTHON -m pip install psutil rich gputil py-cpuinfo flask -q
  success "Packages installed"
fi

# ── Verify key imports ────────────────────────────────────────────────────────
info "Verifying installations..."
FAILED=()
for PKG in psutil rich GPUtil flask cpuinfo; do
  if $PYTHON -c "import $PKG" &>/dev/null; then
    success "  $PKG ✓"
  else
    FAILED+=("$PKG")
    warn "  $PKG — import failed"
  fi
done

if [ ${#FAILED[@]} -gt 0 ]; then
  warn "Some packages failed: ${FAILED[*]}"
  warn "The app will auto-install missing packages on first run."
else
  success "All packages verified"
fi

# ── nvidia-smi check (optional) ───────────────────────────────────────────────
echo ""
info "Checking NVIDIA GPU tools..."
if command -v nvidia-smi &>/dev/null; then
  success "nvidia-smi found — GPU monitoring enabled"
  CUDA=$(nvidia-smi 2>/dev/null | grep "CUDA Version" | awk -F': ' '{print $2}' | awk '{print $1}')
  [ -n "$CUDA" ] && success "  CUDA: $CUDA" || info "  CUDA: not detected"
else
  warn "nvidia-smi not found — NVIDIA GPU stats limited (install NVIDIA drivers for full support)"
fi

# ── Make start.sh executable ──────────────────────────────────────────────────
START_SH="$(dirname "$0")/start.sh"
if [ -f "$START_SH" ]; then
  chmod +x "$START_SH"
  success "start.sh is executable"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║              INSTALLATION COMPLETE ✓                ║"
echo "  ╠══════════════════════════════════════════════════════╣"
if [ "$USE_VENV" = true ]; then
echo "  ║  Virtual env: .venv/                                 ║"
fi
echo "  ║                                                      ║"
echo "  ║  To start the web dashboard:                         ║"
echo "  ║    ./start.sh          — web dashboard (browser)     ║"
echo "  ║    ./start.sh --cli    — terminal output only        ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"
