#!/bin/bash
# Teardown infrastructure
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "[INFO] Stopping infrastructure..."
cd "$ROOT_DIR/docker"
docker compose down -v

echo "[INFO] ✓ Teardown complete"
