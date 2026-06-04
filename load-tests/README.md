# Bomi Pay Load Tests

Performance and load testing suite for the Bomi Pay backend API.  
Two toolchains are provided: **k6** (primary, JavaScript-based) and **Locust** (Python fallback).

---

## Directory Structure

```
load-tests/
├── k6.config.js           # Shared thresholds and base URL
├── scenarios/
│   ├── webhook_ingestion.js   # 100 VUs — POST webhook events
│   ├── dashboard_query.js     # 50 VUs  — GET /dashboard endpoints
│   ├── timeline_query.js      # 50 VUs  — GET /timeline/payments
│   ├── provider_sync.js       # 20 VUs  — POST provider sync jobs
│   ├── transaction_list.js    # 100 VUs — GET /transactions
│   ├── ai_assistant.js        # 10 VUs  — POST /ai-assistant/query
│   └── full_journey.js        # Realistic end-to-end merchant session
├── helpers/
│   ├── auth.js                # Login + Bearer token helpers
│   ├── data.js                # Payload generators
│   └── checks.js              # Reusable k6 check objects
└── scripts/
    ├── run-all.sh             # Run every scenario sequentially
    ├── run-smoke.sh           # 30-second smoke test (3 VUs)
    └── run-soak.sh            # 30-minute soak test (20 VUs sustained)
```

---

## Prerequisites

### k6

```bash
# macOS
brew install k6

# Windows (winget)
winget install k6 --source winget

# Linux
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6

# Docker (no install required)
docker run --rm -i grafana/k6 run - <load-tests/scenarios/full_journey.js
```

### Locust (Python fallback)

```bash
pip install locust
```

---

## Running k6 Tests

### 1. Start the development server

```bash
uvicorn bomipay.main:app --reload --port 8000
```

### 2. Run a single scenario

```bash
# Unauthenticated endpoints (webhook)
k6 run load-tests/scenarios/webhook_ingestion.js

# Authenticated endpoints — supply a token
AUTH_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"yourpass"}' | jq -r .access_token)

AUTH_TOKEN=$AUTH_TOKEN MERCHANT_ID=<your-merchant-id> \
  k6 run load-tests/scenarios/dashboard_query.js
```

### 3. Run the full suite

```bash
AUTH_TOKEN=$AUTH_TOKEN MERCHANT_ID=<id> ./load-tests/scripts/run-all.sh
```

### 4. Smoke test (CI / pre-deploy)

```bash
./load-tests/scripts/run-smoke.sh
```

### 5. Soak test (30 minutes)

```bash
AUTH_TOKEN=$AUTH_TOKEN MERCHANT_ID=<id> ./load-tests/scripts/run-soak.sh
```

### Generate an HTML Report

k6 does not produce HTML directly, but you can use the [k6 reporter](https://github.com/benc-uk/k6-reporter) summary handler:

```bash
k6 run --out json=results/output.json load-tests/scenarios/full_journey.js
# Then open results/output.json in your k6 Cloud or Grafana dashboard,
# or convert with: k6 convert results/output.json > results/report.html
```

---

## Running Locust Tests

```bash
# Interactive web UI (default port 8089)
locust -f tests/test_load_locust.py --host http://localhost:8000

# Headless smoke (10 users, 30s)
locust -f tests/test_load_locust.py --headless -u 10 -r 2 \
  --run-time 30s --host http://localhost:8000 \
  --html results/locust-report.html --csv results/locust-stats

# Full load (100 users, 60s)
locust -f tests/test_load_locust.py --headless -u 100 -r 10 \
  --run-time 60s --host http://localhost:8000 \
  --html results/locust-report.html
```

---

## SLA Thresholds

| Endpoint group         | P95 target | P99 target | Error rate |
|------------------------|-----------|-----------|------------|
| Webhook ingestion      | < 200ms   | < 1000ms  | < 1%       |
| Dashboard              | < 500ms   | < 2000ms  | < 1%       |
| Timeline / transactions| < 500ms   | < 2000ms  | < 1%       |
| Provider sync          | < 1000ms  | < 2000ms  | < 1%       |
| AI assistant           | < 5000ms  | —         | < 1%       |
| Full journey (per req) | < 1000ms  | < 2000ms  | < 1%       |

---

## Expected Baseline Numbers (local SQLite dev setup)

| Scenario              | VUs | RPS (approx) | P95   |
|-----------------------|-----|-------------|-------|
| webhook_ingestion     | 100 | 400–800     | ~80ms |
| dashboard_query       | 50  | 50–100      | ~200ms|
| timeline_query        | 50  | 80–150      | ~150ms|
| transaction_list      | 100 | 150–300     | ~150ms|
| ai_assistant          | 10  | 2–5         | ~500ms|

Production (PostgreSQL + Redis cache) numbers will be higher.

---

## Interpreting Results

k6 outputs a summary to stdout at the end of each run:

```
✓ status is 200
✓ response time < 200ms

checks.........................: 99.80%  ✓ 1200  ✗ 2
data_received..................: 4.5 MB  75 kB/s
data_sent......................: 1.2 MB  20 kB/s
http_req_duration..............: avg=45ms   min=12ms  med=38ms   max=310ms  p(90)=89ms   p(95)=120ms
http_req_failed................: 0.00%   ✓ 0     ✗ 1200
```

- **checks %**: percentage of assertions that passed; aim for > 99%
- **http_req_failed**: rate of non-2xx responses; must stay < 1%
- **p(95)**: 95th percentile latency — the primary SLA metric
- **vus_max**: peak concurrent virtual users observed

If a threshold fails, k6 exits with code 99 (caught by CI).

---

## Adding a New Scenario

1. Create `load-tests/scenarios/my_endpoint.js`
2. Import `defaultThresholds` and `BASE_URL` from `../k6.config.js`
3. Define `export const options = { stages: [...], thresholds: {...} }`
4. Implement `export default function(data) { ... }`
5. Add the scenario name to `scripts/run-all.sh`
6. Document the SLA in the table above

```javascript
// load-tests/scenarios/my_endpoint.js
import http from 'k6/http'
import { check, sleep } from 'k6'
import { defaultThresholds, BASE_URL } from '../k6.config.js'
import { getToken, authHeaders } from '../helpers/auth.js'

export const options = {
  stages: [
    { duration: '20s', target: 10 },
    { duration: '60s', target: 20 },
    { duration: '20s', target: 0  },
  ],
  thresholds: { ...defaultThresholds },
}

export function setup() { return { token: getToken() } }

export default function(data) {
  const res = http.get(`${BASE_URL}/api/v1/my-endpoint`, {
    headers: authHeaders(data.token),
    tags: { endpoint: 'my_endpoint' },
  })
  check(res, { 'status 200': (r) => r.status === 200 })
  sleep(0.1)
}
```
