/**
 * Security Utilities: Data Masking & Sanitization
 *
 * Provides functions to mask sensitive data before display in UI.
 * Used to prevent accidental exposure of PII in frontend.
 */

/**
 * Mask bank account number to show only last 4 digits
 * @param accountNumber - Full account number
 * @returns Masked account number (e.g., ••••7890)
 */
export function maskAccountNumber(accountNumber: string | null | undefined): string {
  if (!accountNumber || accountNumber.length < 4) {
    return '••••'
  }
  return `••••${accountNumber.slice(-4)}`
}

/**
 * Mask phone number to show only last 4 digits
 * @param phone - Full phone number
 * @returns Masked phone (e.g., +234-••••-5678)
 */
export function maskPhoneNumber(phone: string | null | undefined): string {
  if (!phone || phone.length < 4) {
    return '••••••••'
  }
  return `${phone.slice(0, -4)}••••`
}

/**
 * Mask email to show first letter and domain
 * @param email - Full email address
 * @returns Masked email (e.g., j••••••••••@example.com)
 */
export function maskEmail(email: string | null | undefined): string {
  if (!email || !email.includes('@')) {
    return '••••@••••'
  }
  const [localPart, domain] = email.split('@')
  if (localPart.length <= 1) {
    return `${localPart}••••@${domain}`
  }
  return `${localPart[0]}${'•'.repeat(Math.min(10, localPart.length - 1))}@${domain}`
}

/**
 * Mask credit card number to show only last 4 digits
 * @param cardNumber - Full card number (digits only or with spaces/dashes)
 * @returns Masked card (e.g., •••• •••• •••• 5678)
 */
export function maskCardNumber(cardNumber: string | null | undefined): string {
  if (!cardNumber) {
    return '•••• •••• •••• ••••'
  }
  const clean = cardNumber.replace(/\s+/g, '').replace(/-/g, '')
  if (clean.length < 4) {
    return '•••• •••• •••• ••••'
  }
  const lastFour = clean.slice(-4)
  return `•••• •••• •••• ${lastFour}`
}

/**
 * Truncate bank description to prevent exposure of account numbers in text
 * Common pattern: "PAYSTACK SETTLEMENT to ACCOUNT 1234567890"
 * Removes numeric sequences that might be account numbers
 * @param description - Bank statement description
 * @returns Sanitized description
 */
export function sanitizeBankDescription(description: string | null | undefined): string {
  if (!description) {
    return 'Bank Transfer'
  }

  // Remove sequences of 10+ consecutive digits (likely account numbers)
  let sanitized = description.replace(/\d{10,}/g, '****')

  // Remove patterns like "ACCOUNT xxxxxxxx" or "ACCT xxxxxxxx"
  sanitized = sanitized.replace(/(?:ACCOUNT|ACCT)\s+\d+/gi, 'ACCOUNT ****')

  // Remove patterns like "REF: xxxxxxx"
  sanitized = sanitized.replace(/REF:\s+\S+/gi, 'REF: ****')

  return sanitized
}

/**
 * Mask merchant ID or reference for audit logs
 * @param id - Full ID/reference
 * @returns Masked ID showing first 3 and last 4 chars
 */
export function maskMerchantId(id: string | null | undefined): string {
  if (!id || id.length < 7) {
    return '••••••••'
  }
  return `${id.slice(0, 3)}•••••••${id.slice(-4)}`
}

export default {
  maskAccountNumber,
  maskPhoneNumber,
  maskEmail,
  maskCardNumber,
  sanitizeBankDescription,
  maskMerchantId,
}
