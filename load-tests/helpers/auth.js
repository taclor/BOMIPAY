/**
 * Auth helper — login once per VU and cache the token.
 *
 * Usage:
 *   import { getToken, authHeaders } from '../helpers/auth.js'
 *
 *   export function setup() { return { token: getToken() } }
 *   export default function(data) {
 *     const res = http.get(url, { headers: authHeaders(data.token) })
 *   }
 */

import http from 'k6/http'
import { BASE_URL } from '../k6.config.js'

const LOAD_TEST_EMAIL = __ENV.LOAD_TEST_EMAIL || 'load_test@example.com'
const LOAD_TEST_PASSWORD = __ENV.LOAD_TEST_PASSWORD || 'LoadTest123!'

/**
 * Obtain a JWT access token by logging in.
 * Call this from the k6 `setup()` lifecycle function so it runs once.
 *
 * @returns {string} JWT access token, or empty string on failure.
 */
export function getToken() {
  const res = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ email: LOAD_TEST_EMAIL, password: LOAD_TEST_PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } }
  )
  if (res.status === 200) {
    return res.json('access_token') || ''
  }
  // Fall back to env var if login endpoint unavailable during k6 setup
  return __ENV.AUTH_TOKEN || ''
}

/**
 * Build HTTP headers with Bearer token.
 *
 * @param {string} token
 * @returns {Object}
 */
export function authHeaders(token) {
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  }
}
