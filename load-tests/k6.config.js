/**
 * Shared k6 configuration: thresholds, base URL, and common options.
 * Import these into each scenario file.
 */

export const defaultThresholds = {
  // HTTP error rate must be < 1%
  http_req_failed: [{ threshold: 'rate<0.01', abortOnFail: true }],

  // 95th percentile response time < 500ms for most endpoints
  http_req_duration: [
    { threshold: 'p(95)<500', abortOnFail: false },
    { threshold: 'p(99)<2000', abortOnFail: false },
  ],

  // Webhook endpoint specifically must handle high throughput
  'http_req_duration{endpoint:webhook}': [
    { threshold: 'p(95)<200', abortOnFail: false },
  ],

  // Dashboard query < 500ms P95
  'http_req_duration{endpoint:dashboard}': [
    { threshold: 'p(95)<500', abortOnFail: false },
  ],

  // Timeline and transaction queries
  'http_req_duration{endpoint:timeline}': [
    { threshold: 'p(95)<500', abortOnFail: false },
  ],
  'http_req_duration{endpoint:transactions}': [
    { threshold: 'p(95)<500', abortOnFail: false },
  ],

  // Provider sync can be slightly slower
  'http_req_duration{endpoint:provider_sync}': [
    { threshold: 'p(95)<1000', abortOnFail: false },
  ],

  // AI assistant can be much slower
  'http_req_duration{endpoint:ai}': [
    { threshold: 'p(95)<5000', abortOnFail: false },
  ],
}

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000'
export const MERCHANT_ID = __ENV.MERCHANT_ID || 'test-merchant-id'
export const AUTH_TOKEN = __ENV.AUTH_TOKEN || ''

/**
 * Smoke test options — used by run-smoke.sh.
 * Low VU count, short duration, same thresholds.
 */
export const smokeOptions = {
  vus: 3,
  duration: '30s',
  thresholds: defaultThresholds,
}

/**
 * Soak test options — used by run-soak.sh.
 * Sustained moderate load over 30 minutes.
 */
export const soakOptions = {
  stages: [
    { duration: '5m',  target: 20 },
    { duration: '20m', target: 20 },
    { duration: '5m',  target: 0  },
  ],
  thresholds: {
    ...defaultThresholds,
    // Soak allows slightly looser P99 for memory-growth scenarios
    http_req_duration: [
      { threshold: 'p(95)<800',  abortOnFail: false },
      { threshold: 'p(99)<3000', abortOnFail: false },
    ],
  },
}
