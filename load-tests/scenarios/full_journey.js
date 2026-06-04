/**
 * Scenario: Full Journey
 *
 * Simulates a complete, realistic merchant session:
 *   1. Load dashboard (mission control)
 *   2. Check provider health metrics
 *   3. List recent incidents
 *   4. Browse payment timeline
 *   5. Check action center
 *   6. Submit an AI query
 *   7. List recent transactions
 *
 * SLA: P95 for the full journey < 1000ms per individual request.
 *
 * Run:
 *   AUTH_TOKEN=<token> MERCHANT_ID=<id> k6 run load-tests/scenarios/full_journey.js
 */

import http from 'k6/http'
import { check, sleep, group } from 'k6'
import { BASE_URL, MERCHANT_ID } from '../k6.config.js'
import { getToken, authHeaders } from '../helpers/auth.js'
import { checkOk, checkNoServerError } from '../helpers/checks.js'
import { AI_QUERIES, randomChoice } from '../helpers/data.js'

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '60s', target: 20 },
    { duration: '30s', target: 0  },
  ],
  thresholds: {
    http_req_failed: [{ threshold: 'rate<0.01', abortOnFail: true }],
    // Individual requests within a journey can be up to 1s P95
    http_req_duration: [{ threshold: 'p(95)<1000', abortOnFail: false }],
  },
}

export function setup() {
  return { token: getToken() }
}

export default function (data) {
  const headers = authHeaders(data.token)
  const m = MERCHANT_ID

  group('1. dashboard', () => {
    const res = http.get(
      `${BASE_URL}/api/v1/dashboard?merchant_id=${m}`,
      { headers, tags: { endpoint: 'dashboard' } }
    )
    check(res, { ...checkOk, ...checkNoServerError })
    sleep(0.2)
  })

  group('2. provider health', () => {
    const res = http.get(
      `${BASE_URL}/api/v1/provider-health/metrics?merchant_id=${m}`,
      { headers, tags: { endpoint: 'dashboard' } }
    )
    check(res, { ...checkNoServerError })
    sleep(0.1)
  })

  group('3. incidents', () => {
    const res = http.get(
      `${BASE_URL}/api/v1/incidents?merchant_id=${m}&limit=10`,
      { headers, tags: { endpoint: 'dashboard' } }
    )
    check(res, { ...checkNoServerError })
    sleep(0.2)
  })

  group('4. timeline', () => {
    const res = http.get(
      `${BASE_URL}/api/v1/timeline/payments?merchant_id=${m}&limit=20`,
      { headers, tags: { endpoint: 'timeline' } }
    )
    check(res, { ...checkOk, ...checkNoServerError })
    sleep(0.2)
  })

  group('5. action center', () => {
    const res = http.get(
      `${BASE_URL}/api/v1/action-center?merchant_id=${m}`,
      { headers, tags: { endpoint: 'dashboard' } }
    )
    check(res, { ...checkNoServerError })
    sleep(0.1)
  })

  group('6. ai assistant', () => {
    const res = http.post(
      `${BASE_URL}/api/v1/ai-assistant/query`,
      JSON.stringify({ merchant_id: m, query: randomChoice(AI_QUERIES) }),
      { headers, tags: { endpoint: 'ai' }, timeout: '10s' }
    )
    check(res, { ...checkNoServerError })
    sleep(0.5)
  })

  group('7. transactions', () => {
    const res = http.get(
      `${BASE_URL}/api/v1/transactions?status=success`,
      { headers, tags: { endpoint: 'transactions' } }
    )
    check(res, { ...checkOk, ...checkNoServerError })
    sleep(0.1)
  })

  // Think-time between full sessions
  sleep(1)
}
