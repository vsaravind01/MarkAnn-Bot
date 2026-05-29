#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

mkdir -p "$LOG_DIR"

GRN='\033[0;32m'; CYN='\033[0;36m'; YLW='\033[1;33m'
RED='\033[0;31m'; BLD='\033[1m'; RST='\033[0m'

PIDS=()
NAMES=()

cleanup() {
  echo -e "\n${YLW}Shutting down...${RST}"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "All services stopped."
}
trap cleanup EXIT INT TERM

cd "$PROJECT_ROOT"

echo -e "${BLD}MarkAnn — dev stack${RST}"
echo -e "Logs → ${CYN}scripts/logs/${RST}\n"

# ── Backend :1530  (15:30 — NSE closes) ─────────────────────────────────────
uv run uvicorn api.app:app \
  --port 1530 \
  --reload \
  > "$LOG_DIR/backend.log" 2>&1 &
PIDS+=($!)
NAMES+=("backend")
echo -e "  ${GRN}↑${RST} backend   :${BLD}1530${RST}  →  scripts/logs/backend.log"

# ── Gateway :9150  (09:15 — NSE opens) ──────────────────────────────────────
BACKEND_URL=http://localhost:1530 \
  uv run uvicorn gateway.main:app \
  --port 9150 \
  --reload \
  > "$LOG_DIR/gateway.log" 2>&1 &
PIDS+=($!)
NAMES+=("gateway")
echo -e "  ${GRN}↑${RST} gateway   :${BLD}9150${RST}  →  scripts/logs/gateway.log"

# ── Frontend :5173 ───────────────────────────────────────────────────────────
(cd "$PROJECT_ROOT/app/admin" && npm run dev) \
  > "$LOG_DIR/frontend.log" 2>&1 &
PIDS+=($!)
NAMES+=("frontend")
echo -e "  ${GRN}↑${RST} frontend  :${BLD}5173${RST}  →  scripts/logs/frontend.log"

# Wait briefly then verify all three processes are still alive
sleep 2

echo
failed=false
for i in "${!PIDS[@]}"; do
  if ! kill -0 "${PIDS[$i]}" 2>/dev/null; then
    echo -e "  ${RED}✗${RST} ${NAMES[$i]} exited early — check scripts/logs/${NAMES[$i]}.log"
    failed=true
  fi
done

if [ "$failed" = false ]; then
  echo -e "  ${GRN}✓${RST} All services running"
fi

echo -e "\n  ${CYN}http://localhost:5173${RST}  •  Ctrl+C to stop all\n"

wait
