/**
 * Test data generators for load test scenarios.
 *
 * Usage:
 *   import { randomRef, paystackWebhookPayload } from '../helpers/data.js'
 */

import { MERCHANT_ID } from '../k6.config.js'

/**
 * Generate a unique-ish reference string for a VU iteration.
 * k6 globals __VU and __ITER are available at runtime.
 */
export function randomRef(prefix = 'ref') {
  return `${prefix}_${__VU}_${__ITER}_${Date.now()}`
}

/**
 * Build a realistic Paystack charge.success webhook payload.
 *
 * @param {string} merchantId
 * @returns {string} JSON string
 */
export function paystackWebhookPayload(merchantId) {
  return JSON.stringify({
    event: 'charge.success',
    data: {
      id: Math.floor(Math.random() * 9_000_000) + 1_000_000,
      reference: randomRef('txn'),
      amount: 500_000,                // 5,000 NGN in kobo
      currency: 'NGN',
      status: 'success',
      channel: 'card',
      gateway_response: 'Approved',
      paid_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      transaction_date: new Date().toISOString(),
      customer: {
        email: 'load@test.com',
        phone: '+2348000000001',
        first_name: 'Load',
        last_name: 'Test',
      },
      metadata: { merchant_id: merchantId || MERCHANT_ID },
    },
  })
}

/**
 * Build a Flutterwave payment.completed webhook payload.
 */
export function flutterwaveWebhookPayload(merchantId) {
  return JSON.stringify({
    event: 'charge.completed',
    data: {
      id: Math.floor(Math.random() * 9_000_000) + 1_000_000,
      tx_ref: randomRef('flw'),
      flw_ref: randomRef('flw_ref'),
      amount: 5000,
      currency: 'NGN',
      status: 'successful',
      payment_type: 'card',
      customer: { email: 'load@test.com', name: 'Load Test' },
      meta: { merchant_id: merchantId || MERCHANT_ID },
    },
  })
}

/**
 * Pick a random item from an array.
 */
export function randomChoice(arr) {
  return arr[Math.floor(Math.random() * arr.length)]
}

/** Sample AI queries for load testing */
export const AI_QUERIES = [
  'What is the current payment success rate?',
  'Show me failed transactions in the last hour',
  'Which provider has the best uptime today?',
  'Summarise payment anomalies this week',
  'How many NGN transactions were processed today?',
]
