#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SRC_DIR="${REPO_ROOT}/schemas"
DEST_DIR="${REPO_ROOT}/pkg/store/schemas"

if [[ "${1:-}" == "--check" ]]; then
  echo "Checking for drift between ${SRC_DIR} and ${DEST_DIR}..."
  if ! diff -r "${SRC_DIR}" "${DEST_DIR}"; then
    echo "ERROR: Schemas in ${DEST_DIR} do not match ${SRC_DIR}."
    echo "Run ./scripts/sync-schemas.sh to sync them."
    exit 1
  fi
  echo "Schemas are in sync."
  exit 0
fi

echo "Syncing schemas from ${SRC_DIR} to ${DEST_DIR}..."
mkdir -p "${DEST_DIR}"
cp -f "${SRC_DIR}"/*.json "${DEST_DIR}/"
echo "Schemas synced successfully."
