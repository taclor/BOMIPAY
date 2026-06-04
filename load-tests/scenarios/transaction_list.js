/**
 * Scenario: Transaction List
 *
 * Simulates 100 concurrent users fetching paginated transaction lists
 * with various filter combinations.
 * SLA: P95 < 500ms.
 *
 * Run:
 *   AUTH_TOKEN=<token> k6 run load-tests/scenarios/transaction_list.js
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import { defaultThresholds, BASE_URL } from '../k6.config.js'
import { getToken, authHeaders } from '../helpers/auth.js'
import { checkOk, checkNoServerError } from '../helpers/checks.js'

export const options = {
  stages: [
    { duration: '30s', target: 50  },
    { duration: '60s', target: 100 },
    { duration: '30s', target: 0   },
  ],
  thresholds: {
    ...defaultThresholds,
    'http_req_duration{endpoint:transactions}': [
      { threshold: 'p(95)<500', abortOnFail: false },
    ],
  },
}

export function setup() {
  return { token: getToken() }
}

export default function (data) {
  const headers = authHeaders(data.token)

  // Rotate through filter variants to exercise multiple query plans
  const filters = [
    '',
    '?status=success',
    '?status=failed',
    '?provider_name=paystack',
    '?status=success&provider_name=paystack',
  ]

  const filter = filters[__ITER % filters.length]
  const url = `${BASE_URL}/api/v1/transactions${filter}`

  const res = http.get(url, {
    headers,
    tags: { endpoint: 'transactions' },
  })

  check(res, {
    ...checkOk,
    ...checkNoServerError,
    'response is array': (r) => {
      try { return Array.isArray(r.json()) } catch (_) { return false }
    },
  })

  sleep(0.05)
}
