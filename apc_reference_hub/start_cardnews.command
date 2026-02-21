#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8512}"

( sleep 2; open "http://127.0.0.1:${PORT}" ) >/dev/null 2>&1 &
"${SCRIPT_DIR}/run_cardnews_web.sh"
