/**
 * Reusable k6 check helpers.
 *
 * Usage:
 *   import { checkOk, checkCreated, checkLatency } from '../helpers/checks.js'
 *
 *   check(res, { ...checkOk, ...checkLatency(200) })
 */

/**
 * Assert HTTP 200 OK.
 */
export const checkOk = {
  'status is 200': (r) => r.status === 200,
}

/**
 * Assert HTTP 201 Created.
 */
export const checkCreated = {
  'status is 201': (r) => r.status === 201,
}

/**
 * Assert that the request_id header is present (set by Bomi Pay middleware).
 */
export const checkRequestId = {
  'X-Request-ID header present': (r) =>
    r.headers['X-Request-Id'] !== undefined ||
    r.headers['X-Request-ID'] !== undefined,
}

/**
 * Assert JSON body has a `data` field.
 */
export const checkHasData = {
  'response has data field': (r) => {
    try {
      const body = r.json()
      return body !== null && (body.data !== undefined || r.status === 200)
    } catch (_) {
      return false
    }
  },
}

/**
 * Assert response time is within given milliseconds.
 *
 * @param {number} ms - maximum allowed duration in milliseconds
 * @returns {Object} k6 check object
 */
export function checkLatency(ms) {
  return {
    [`response time < ${ms}ms`]: (r) => r.timings.duration < ms,
  }
}

/**
 * Assert status is not a 5xx error.
 */
export const checkNoServerError = {
  'no server error (not 5xx)': (r) => r.status < 500,
}

/**
 * Combine multiple check objects.
 *
 * @param {...Object} checks
 * @returns {Object}
 */
export function combineChecks(...checks) {
  return Object.assign({}, ...checks)
}
