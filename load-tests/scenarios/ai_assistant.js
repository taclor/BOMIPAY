/**
 * Scenario: AI Assistant Query
 *
 * Simulates 10 concurrent users querying the AI assistant.
 * The AI endpoint is intentionally allowed to be slow (P95 < 5000ms).
 *
 * Run:
 *   AUTH_TOKEN=<token> MERCHANT_ID=<id> k6 run load-tests/scenarios/ai_assistant.js
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import { defaultThresholds, BASE_URL, MERCHANT_ID } from '../k6.config.js'
import { getToken, authHeaders } from '../helpers/auth.js'
import { checkNoServerError } from '../helpers/checks.js'
import { AI_QUERIES, randomChoice } from '../helpers/data.js'

export const options = {
  stages: [
    { duration: '15s', target: 5  },
    { duration: '60s', target: 10 },
    { duration: '15s', target: 0  },
  ],
  thresholds: {
    ...defaultThresholds,
    // AI endpoint gets its own lenient SLA
    'http_req_duration{endpoint:ai}': [
      { threshold: 'p(95)<5000', abortOnFail: false },
    ],
  },
}

export function setup() {
  return { token: getToken() }
}

export default function (data) {
  const headers = authHeaders(data.token)

  const res = http.post(
    `${BASE_URL}/api/v1/ai-assistant/query`,
    JSON.stringify({
      merchant_id: MERCHANT_ID,
      query: randomChoice(AI_QUERIES),
    }),
    {
      headers,
      tags: { endpoint: 'ai' },
      timeout: '10s',
    }
  )

  check(res, {
    ...checkNoServerError,
    'ai query accepted': (r) =>
      r.status === 200 || r.status === 422 || r.status === 401,
  })

  // AI requests are naturally slow; back off between iterations
  sleep(1)
}
