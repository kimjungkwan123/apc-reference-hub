#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8511}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_DATA_DIR="${SCRIPT_DIR}/data_store"
APC_HUB_DATA_DIR="${APC_HUB_DATA_DIR:-$DEFAULT_DATA_DIR}"
export APC_HUB_DATA_DIR
mkdir -p "${APC_HUB_DATA_DIR}"

exec streamlit run app.py \
  --server.headless true \
  --server.address 0.0.0.0 \
  --server.port "${PORT}" \
  --browser.gatherUsageStats false
