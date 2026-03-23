#!/usr/bin/env bash
# =============================================================================
# HireRight AI — One-Click Launcher
# Usage:
#   ./run_hireright.sh          Start everything
#   ./run_hireright.sh stop     Stop everything
#   ./run_hireright.sh logs     Tail all logs live
#   ./run_hireright.sh status   Check what's running
# =============================================================================
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV="$ROOT_DIR/venv/bin/python"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}ℹ  $*${RESET}"; }
success() { echo -e "${GREEN}✅ $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠  $*${RESET}"; }
error()   { echo -e "${RED}❌ $*${RESET}"; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

# ── Stop ─────────────────────────────────────────────────────────────────────
do_stop() {
    header "Stopping HireRight AI services..."
    pkill -f "mcp_servers/github-context/server.py" 2>/dev/null && info "GitHub MCP stopped"    || true
    pkill -f "mcp_servers/job-market/server.py"     2>/dev/null && info "Job Market MCP stopped" || true
    pkill -f "uvicorn app.main:app"                 2>/dev/null && info "Backend stopped"        || true
    pkill -f "streamlit run.*frontend/app.py"       2>/dev/null && info "Frontend stopped"       || true
    success "All services stopped."
}

# ── Status ───────────────────────────────────────────────────────────────────
do_status() {
    header "HireRight AI — Service Status"
    check_port() {
        local name=$1 port=$2
        if lsof -ti :"$port" &>/dev/null; then
            echo -e "  ${GREEN}● $name${RESET} (port $port)"
        else
            echo -e "  ${RED}○ $name${RESET} (port $port — not running)"
        fi
    }
    check_port "GitHub Context MCP" 8001
    check_port "Job Market MCP"     8002
    check_port "FastAPI Backend"    8000
    check_port "Streamlit Frontend" 8501
}

# ── Logs ─────────────────────────────────────────────────────────────────────
do_logs() {
    header "Tailing all logs (Ctrl+C to stop)..."
    tail -f \
        "$LOG_DIR/mcp_github.log" \
        "$LOG_DIR/mcp_jobmarket.log" \
        "$LOG_DIR/backend.log" \
        "$LOG_DIR/frontend.log" 2>/dev/null \
    || warn "Some log files not found yet — start the services first."
}

# ── Health check ─────────────────────────────────────────────────────────────
wait_for_port() {
    local name=$1 port=$2 max_wait=${3:-20}
    local i=0
    while ! lsof -ti :"$port" &>/dev/null; do
        sleep 1
        i=$((i+1))
        if [ $i -ge $max_wait ]; then
            warn "$name did not start on port $port within ${max_wait}s — check logs/$( echo "$name" | tr ' ' '_' | tr '[:upper:]' '[:lower:]').log"
            return 1
        fi
    done
    success "$name is up on port $port"
}

# ── Start ─────────────────────────────────────────────────────────────────────
do_start() {
    header "🎯 HireRight AI — Starting all services"

    # ── Pre-flight checks ──
    if [ ! -d "$ROOT_DIR/venv" ]; then
        error "Virtual environment not found at $ROOT_DIR/venv"
        echo    "  Create it with:  python3.11 -m venv venv && venv/bin/pip install -e '.[frontend]'"
        exit 1
    fi

    if [ ! -f "$ROOT_DIR/.env" ]; then
        warn ".env file not found — API keys will be missing. Create one from .env.example if available."
    fi

    # ── Kill any stale processes ──
    info "Cleaning up any stale processes..."
    pkill -f "mcp_servers/github-context/server.py" 2>/dev/null || true
    pkill -f "mcp_servers/job-market/server.py"     2>/dev/null || true
    pkill -f "uvicorn app.main:app"                 2>/dev/null || true
    pkill -f "streamlit run.*frontend/app.py"       2>/dev/null || true
    sleep 1

    # ── 1. GitHub Context MCP (port 8001) ──
    header "1/4 — GitHub Context MCP Server (port 8001)"
    nohup "$VENV" "$ROOT_DIR/mcp_servers/github-context/server.py" \
        > "$LOG_DIR/mcp_github.log" 2>&1 &
    wait_for_port "GitHub Context MCP" 8001 15

    # ── 2. Job Market MCP (port 8002) ──
    header "2/4 — Job Market MCP Server (port 8002)"
    nohup "$VENV" "$ROOT_DIR/mcp_servers/job-market/server.py" \
        > "$LOG_DIR/mcp_jobmarket.log" 2>&1 &
    wait_for_port "Job Market MCP" 8002 15

    # ── 3. FastAPI Backend (port 8000) ──
    header "3/4 — FastAPI Backend (port 8000)"
    (
        cd "$ROOT_DIR/backend"
        nohup "$VENV" -m uvicorn app.main:app \
            --host 0.0.0.0 --port 8000 --reload \
            > "$LOG_DIR/backend.log" 2>&1
    ) &
    wait_for_port "FastAPI Backend" 8000 25

    # ── 4. Streamlit Frontend (port 8501) ──
    header "4/4 — Streamlit Frontend (port 8501)"
    nohup "$VENV" -m streamlit run "$ROOT_DIR/frontend/app.py" \
        --server.port 8501 \
        --server.headless true \
        > "$LOG_DIR/frontend.log" 2>&1 &
    wait_for_port "Streamlit Frontend" 8501 25

    # ── Summary ──
    echo ""
    echo -e "${BOLD}════════════════════════════════════════${RESET}"
    echo -e "${GREEN}${BOLD}  HireRight AI is running!${RESET}"
    echo -e "${BOLD}════════════════════════════════════════${RESET}"
    echo -e "  ${CYAN}Frontend UI${RESET}  →  http://localhost:8501"
    echo -e "  ${CYAN}API Docs   ${RESET}  →  http://localhost:8000/docs"
    echo -e "  ${CYAN}GitHub MCP ${RESET}  →  http://localhost:8001/health"
    echo -e "  ${CYAN}Job MCP    ${RESET}  →  http://localhost:8002/health"
    echo -e "${BOLD}════════════════════════════════════════${RESET}"
    echo ""
    echo -e "  ${YELLOW}Logs${RESET}  →  $LOG_DIR/"
    echo -e "  Tail all:  ${CYAN}./run_hireright.sh logs${RESET}"
    echo -e "  Stop all:  ${CYAN}./run_hireright.sh stop${RESET}"
    echo ""
}

# ── Entry point ──────────────────────────────────────────────────────────────
case "${1:-start}" in
    start)  do_start  ;;
    stop)   do_stop   ;;
    logs)   do_logs   ;;
    status) do_status ;;
    restart)
        do_stop
        sleep 2
        do_start
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status}"
        exit 1
        ;;
esac
