#!/usr/bin/env bash
# =============================================================================
#  AI PC Suitability Checker — Start Script
#  Works on: Linux, macOS, Windows (Git Bash / WSL)
#  Usage:
#    ./start.sh           — launch web dashboard (opens browser automatically)
#    ./start.sh --cli     — run terminal / CLI version instead
#    ./start.sh --help    — show usage
#
#  Windows users: This script requires bash.
#    Option 1: Install Git for Windows (includes bash)
#              https://git-scm.com/download/win
#              Then run: "C:\Program Files\Git\bin\bash.exe" start.sh
#    Option 2: Enable WSL then run: wsl bash start.sh
#    Option 3: Use start.bat instead (works without bash - auto-detects both)
# =============================================================================

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
echo "  ║       AI PC SUITABILITY CHECKER — STARTING          ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Help ──────────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  echo -e "  ${BOLD}Usage:${RESET}"
  echo "    ./start.sh             Launch web dashboard (browser opens automatically)"
  echo "    ./start.sh --cli       Run CLI terminal version"
  echo "    ./start.sh --help      Show this message"
  echo ""
  echo -e "  ${BOLD}Requirements:${RESET}"
  echo "    Run ./install.sh first if you haven't already."
  echo ""
  exit 0
fi

# ── Locate script directory ───────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Detect OS ─────────────────────────────────────────────────────────────────
OS="unknown"
case "$(uname -s)" in
  Linux*)   OS="linux"           ;;
  Darwin*)  OS="macos"           ;;
  CYGWIN*)  OS="windows_cygwin"  ;;
  MINGW*)   OS="windows_gitbash" ;;
  MSYS*)    OS="windows_msys"    ;;
esac

# ── Activate venv if present ──────────────────────────────────────────────────
VENV_DIR="$SCRIPT_DIR/.venv"
if [ -d "$VENV_DIR" ]; then
  if [[ "$OS" == windows* ]]; then
    ACTIVATE="$VENV_DIR/Scripts/activate"
  else
    ACTIVATE="$VENV_DIR/bin/activate"
  fi
  if [ -f "$ACTIVATE" ]; then
    # shellcheck disable=SC1090
    source "$ACTIVATE"
    success "Virtual environment activated: .venv/"
  fi
fi

# ── Resolve Python executable ─────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python python3.11 python3.10 python3.9; do
  if command -v "$cmd" &>/dev/null; then
    VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    MAJOR=$(echo "$VER" | cut -d. -f1)
    MINOR=$(echo "$VER" | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
      PYTHON="$cmd"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  error "Python 3.9+ not found. Run ./install.sh first."
fi

info "Python: $($PYTHON --version)"

# ── Verify required files exist ───────────────────────────────────────────────
MODE="${1:-}"

if [ "$MODE" = "--cli" ]; then
  TARGET="ai_pc_checker.py"
else
  TARGET="ai_pc_web.py"
fi

if [ ! -f "$SCRIPT_DIR/$TARGET" ]; then
  error "$TARGET not found in $SCRIPT_DIR"
fi

# ── Trap Ctrl+C for clean shutdown ────────────────────────────────────────────
cleanup() {
  echo ""
  echo -e "${YELLOW}  Shutting down... (Ctrl+C received)${RESET}"
  echo ""
  # Kill the Python process group if any child is alive
  kill 0 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# ── Launch ────────────────────────────────────────────────────────────────────
if [ "$MODE" = "--cli" ]; then
  echo ""
  echo -e "${BOLD}  Running CLI checker...${RESET}"
  echo ""
  "$PYTHON" "$SCRIPT_DIR/ai_pc_checker.py"
else
  echo ""
  info "Starting web dashboard..."
  info "A browser window will open automatically."
  info "Press Ctrl+C to stop the server."
  echo ""

  # Run the web app (it internally finds a free port and opens the browser)
  "$PYTHON" "$SCRIPT_DIR/ai_pc_web.py"
fi
