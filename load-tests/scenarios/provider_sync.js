/**
 * Scenario: Provider Sync
 *
 * Simulates 20 concurrent finance users triggering provider sync jobs.
 * Uses the POST /provider-sync/{provider_account_id}/transactions endpoint.
 * Requires PROVIDER_ACCOUNT_ID env var pointing to a seeded test account.
 *
 * Run:
 *   AUTH_TOKEN=<token> PROVIDER_ACCOUNT_ID=<id> k6 run load-tests/scenarios/provider_sync.js
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import { defaultThresholds, BASE_URL } from '../k6.config.js'
import { getToken, authHeaders } from '../helpers/auth.js'
import { checkNoServerError } from '../helpers/checks.js'

const PROVIDER_ACCOUNT_ID = __ENV.PROVIDER_ACCOUNT_ID || 'test-provider-account-id'

export const options = {
  stages: [
    { duration: '15s', target: 10 },
    { duration: '60s', target: 20 },
    { duration: '15s', target: 0  },
  ],
  thresholds: {
    ...defaultThresholds,
    'http_req_duration{endpoint:provider_sync}': [
      { threshold: 'p(95)<1000', abortOnFail: false },
    ],
  },
}

export function setup() {
  return { token: getToken() }
}

export default function (data) {
  const headers = authHeaders(data.token)

  const res = http.post(
    `${BASE_URL}/api/v1/provider-sync/${PROVIDER_ACCOUNT_ID}/transactions`,
    JSON.stringify({ force: false }),
    {
      headers,
      tags: { endpoint: 'provider_sync' },
    }
  )

  check(res, {
    ...checkNoServerError,
    'sync accepted or not-found': (r) =>
      r.status === 200 || r.status === 201 || r.status === 404 || r.status === 422,
  })

  sleep(0.5)
}
