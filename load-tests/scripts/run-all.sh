#!/usr/bin/env bash
# Run the full k6 load test suite sequentially.
# Each scenario runs independently; results are written to load-tests/results/.
#
# Usage:
#   cd load-tests && ./scripts/run-all.sh
#   BASE_URL=http://api.example.com AUTH_TOKEN=<jwt> ./scripts/run-all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="${SUITE_DIR}/results"

mkdir -p "$RESULTS_DIR"

export BASE_URL="${BASE_URL:-http://localhost:8000}"
export MERCHANT_ID="${MERCHANT_ID:-test-merchant-id}"
export AUTH_TOKEN="${AUTH_TOKEN:-}"
export PAYSTACK_WEBHOOK_SECRET="${PAYSTACK_WEBHOOK_SECRET:-test-paystack-secret}"

SCENARIOS=(
  "webhook_ingestion"
  "dashboard_query"
  "timeline_query"
  "provider_sync"
  "transaction_list"
  "ai_assistant"
  "full_journey"
)

echo "==> Bomi Pay Load Test Suite"
echo "    BASE_URL: $BASE_URL"
echo "    Results:  $RESULTS_DIR"
echo ""

FAILED=()
for scenario in "${SCENARIOS[@]}"; do
  echo "--- Running: $scenario"
  if k6 run \
      --out "json=${RESULTS_DIR}/${scenario}.json" \
      "${SUITE_DIR}/scenarios/${scenario}.js"; then
    echo "    PASS: $scenario"
  else
    echo "    FAIL: $scenario"
    FAILED+=("$scenario")
  fi
  echo ""
done

if [ ${#FAILED[@]} -gt 0 ]; then
  echo "==> FAILED scenarios: ${FAILED[*]}"
  exit 1
else
  echo "==> All scenarios passed."
fi
