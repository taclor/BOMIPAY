#!/usr/bin/env bash
# 30-minute soak test — sustained moderate load to detect memory leaks,
# connection pool exhaustion, and gradual performance degradation.
#
# Usage:
#   BASE_URL=http://localhost:8000 AUTH_TOKEN=<jwt> ./scripts/run-soak.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="${SUITE_DIR}/results/soak"

mkdir -p "$RESULTS_DIR"

export BASE_URL="${BASE_URL:-http://localhost:8000}"
export MERCHANT_ID="${MERCHANT_ID:-test-merchant-id}"
export AUTH_TOKEN="${AUTH_TOKEN:-}"
export PAYSTACK_WEBHOOK_SECRET="${PAYSTACK_WEBHOOK_SECRET:-test-paystack-secret}"

echo "==> Soak Test  (ramp 5m → 20 VUs, sustain 20m, ramp-down 5m)"
echo "    BASE_URL: $BASE_URL"
echo "    Total duration: ~30 minutes"

# Override options by passing --env flags; k6 will use the soakOptions export
# from full_journey.js when SOAK_TEST=1 env var is set.
k6 run \
  --stage 5m:20 \
  --stage 20m:20 \
  --stage 5m:0 \
  --out "json=${RESULTS_DIR}/soak_$(date +%Y%m%d_%H%M).json" \
  "${SUITE_DIR}/scenarios/full_journey.js"

echo "==> Soak test complete. Check ${RESULTS_DIR} for results."
