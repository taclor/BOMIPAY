/**
 * Scenario: Timeline Query
 *
 * Simulates 50 concurrent users querying the payment timeline with various filters.
 * SLA: P95 < 500ms.
 *
 * Run:
 *   AUTH_TOKEN=<token> MERCHANT_ID=<id> k6 run load-tests/scenarios/timeline_query.js
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import { defaultThresholds, BASE_URL, MERCHANT_ID } from '../k6.config.js'
import { getToken, authHeaders } from '../helpers/auth.js'
import { checkOk, checkNoServerError, checkHasData } from '../helpers/checks.js'

export const options = {
  stages: [
    { duration: '20s', target: 25 },
    { duration: '60s', target: 50 },
    { duration: '20s', target: 0  },
  ],
  thresholds: {
    ...defaultThresholds,
    'http_req_duration{endpoint:timeline}': [
      { threshold: 'p(95)<500', abortOnFail: false },
    ],
  },
}

export function setup() {
  return { token: getToken() }
}

export default function (data) {
  const headers = authHeaders(data.token)
  const base = `${BASE_URL}/api/v1/timeline/payments?merchant_id=${MERCHANT_ID}`

  // Vary queries to exercise different filter paths
  const queries = [
    `${base}&limit=20`,
    `${base}&limit=50&status=success`,
    `${base}&limit=20&status=failed`,
    `${base}&limit=20&provider=paystack`,
  ]

  const url = queries[__VU % queries.length]

  const res = http.get(url, {
    headers,
    tags: { endpoint: 'timeline' },
  })

  check(res, {
    ...checkOk,
    ...checkNoServerError,
    ...checkHasData,
  })

  sleep(0.1)
}
