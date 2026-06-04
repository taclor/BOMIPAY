/**
 * Scenario: Dashboard Query
 *
 * Simulates 50 concurrent merchant users loading the Mission Control dashboard.
 * Exercises /dashboard, /dashboard/metrics, and /dashboard/providers endpoints.
 *
 * Run:
 *   AUTH_TOKEN=<token> MERCHANT_ID=<id> k6 run load-tests/scenarios/dashboard_query.js
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import { defaultThresholds, BASE_URL, MERCHANT_ID } from '../k6.config.js'
import { getToken, authHeaders } from '../helpers/auth.js'
import { checkOk, checkHasData, checkNoServerError } from '../helpers/checks.js'

export const options = {
  stages: [
    { duration: '20s', target: 25 },
    { duration: '60s', target: 50 },
    { duration: '20s', target: 0  },
  ],
  thresholds: {
    ...defaultThresholds,
    'http_req_duration{endpoint:dashboard}': [
      { threshold: 'p(95)<500', abortOnFail: false },
    ],
  },
}

export function setup() {
  return { token: getToken() }
}

export default function (data) {
  const headers = authHeaders(data.token)
  const merchantParam = `merchant_id=${MERCHANT_ID}`

  const endpoints = [
    `/api/v1/dashboard?${merchantParam}`,
    `/api/v1/dashboard/metrics?${merchantParam}`,
    `/api/v1/dashboard/providers?${merchantParam}`,
  ]

  for (const endpoint of endpoints) {
    const res = http.get(`${BASE_URL}${endpoint}`, {
      headers,
      tags: { endpoint: 'dashboard' },
    })

    check(res, {
      ...checkOk,
      ...checkNoServerError,
      ...checkHasData,
    })

    sleep(0.1)
  }
}
