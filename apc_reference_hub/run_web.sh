#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8511}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_DATA_DIR="${SCRIPT_DIR}/data_store"
APC_HUB_DATA_DIR="${APC_HUB_DATA_DIR:-$DEFAULT_DATA_DIR}"
APC_APP="${APC_APP:-hub}"
export APC_HUB_DATA_DIR
mkdir -p "${APC_HUB_DATA_DIR}"

cd "${SCRIPT_DIR}"

APP_FILE="app.py"
if [[ "${APC_APP}" == "cardnews" ]]; then
  APP_FILE="cardnews_app.py"
fi

echo "[run_web] starting ${APP_FILE} on :${PORT}"

exec streamlit run "${APP_FILE}" \
  --server.headless true \
  --server.address 0.0.0.0 \
  --server.port "${PORT}" \
  --browser.gatherUsageStats false
