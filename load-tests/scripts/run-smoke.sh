#!/usr/bin/env bash
# Quick 30-second smoke test — validates key endpoints are responding under
# minimal load before a deployment or in CI pre-merge checks.
#
# Usage:
#   ./scripts/run-smoke.sh
#   BASE_URL=http://staging.example.com AUTH_TOKEN=<jwt> ./scripts/run-smoke.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="${SUITE_DIR}/results/smoke"

mkdir -p "$RESULTS_DIR"

export BASE_URL="${BASE_URL:-http://localhost:8000}"
export MERCHANT_ID="${MERCHANT_ID:-test-merchant-id}"
export AUTH_TOKEN="${AUTH_TOKEN:-}"
export PAYSTACK_WEBHOOK_SECRET="${PAYSTACK_WEBHOOK_SECRET:-test-paystack-secret}"

echo "==> Smoke Test  (3 VUs, 30s)"
echo "    BASE_URL: $BASE_URL"

k6 run \
  --vus 3 \
  --duration 30s \
  --out "json=${RESULTS_DIR}/smoke.json" \
  "${SUITE_DIR}/scenarios/full_journey.js"

echo "==> Smoke test passed."
