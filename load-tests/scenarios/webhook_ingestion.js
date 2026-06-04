/**
 * Scenario: Webhook Ingestion
 *
 * Simulates 100 concurrent VUs submitting Paystack charge.success webhooks.
 * The webhook endpoint must handle high throughput with P95 < 200ms.
 *
 * Run:
 *   k6 run load-tests/scenarios/webhook_ingestion.js
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import crypto from 'k6/crypto'
import { defaultThresholds, BASE_URL } from '../k6.config.js'
import { paystackWebhookPayload } from '../helpers/data.js'
import { checkRequestId, checkNoServerError, checkLatency, combineChecks } from '../helpers/checks.js'

const WEBHOOK_SECRET = __ENV.PAYSTACK_WEBHOOK_SECRET || 'test-paystack-secret'
const MERCHANT_ID = __ENV.MERCHANT_ID || ''

export const options = {
  stages: [
    { duration: '30s', target: 50  },  // Ramp up
    { duration: '60s', target: 100 },  // Sustain 100 VUs
    { duration: '30s', target: 0   },  // Ramp down
  ],
  thresholds: {
    ...defaultThresholds,
    'http_req_duration{endpoint:webhook}': [
      { threshold: 'p(95)<200', abortOnFail: false },
    ],
  },
}

export default function () {
  const payload = paystackWebhookPayload(MERCHANT_ID)
  const signature = crypto.hmac('sha512', payload, WEBHOOK_SECRET, 'hex')

  const res = http.post(
    `${BASE_URL}/webhooks/paystack`,
    payload,
    {
      headers: {
        'Content-Type': 'application/json',
        'X-Paystack-Signature': signature,
      },
      tags: { endpoint: 'webhook' },
    }
  )

  check(
    res,
    combineChecks(
      { 'webhook accepted (200 or 403)': (r) => r.status === 200 || r.status === 403 },
      checkRequestId,
      checkNoServerError,
      checkLatency(200),
    )
  )

  sleep(0.01)
}
