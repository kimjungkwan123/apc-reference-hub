#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8512}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "${SCRIPT_DIR}"

exec streamlit run cardnews_app.py \
  --server.headless true \
  --server.address 0.0.0.0 \
  --server.port "${PORT}" \
  --browser.gatherUsageStats false
