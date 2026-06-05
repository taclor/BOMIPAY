# Bomi Pay Security Posture

**Last Updated:** 2026-01-17  
**Status:** Production-Ready with Mitigation Strategy

---

## Executive Summary

Bomi Pay implements a multi-layered security approach appropriate for **production pilot phase** with a documented migration path to **PCI-DSS compliance** by Q4 2025.

### Security Tier: **Level 2 - Enhanced (Non-PCI Compliant)**
- ✅ Suitable for production with <$10M annual volume
- ⚠️ Requires payment gateway tokens (no direct card handling)
- ❌ Not PCI-DSS compliant (requires Level 1 hardening for compliance)

---

## Authentication & Authorization

### JWT Implementation
- **Algorithm:** HS256 (symmetric) or RS256 (asymmetric, configurable)
- **Access Token Expiry:** 15 minutes (900 seconds)
- **Refresh Token Expiry:** 7 days (604,800 seconds)
- **Token Storage:** localStorage (client-side, see Token Storage section)
- **Issuance:** Upon successful password authentication
- **Revocation:** Tokens revoked on logout; no explicit blacklist (stateless)

### Password Requirements
- **Minimum Length:** 12 characters
- **Complexity:** At least one uppercase, one lowercase, one digit, one special character
- **Hashing:** bcrypt with cost factor 10 (configurable)
- **Storage:** Salted hash only; plaintext never stored
- **Enforcement:** Validated on registration and password change

### Session Management
- **No server-side sessions** (stateless JWT)
- **CSRF Protection:** SameSite=Strict cookie flag when using cookies (roadmap)
- **Concurrent Sessions:** Multiple simultaneous tokens allowed per user
- **Logout:** Client-side token deletion + optional server-side blacklist (future)

---

## Token Storage & Transport

### Current Implementation (Development-Ready)
```typescript
// Frontend: localStorage storage with hydration protection
localStorage.setItem('token', jwt_token)
localStorage.setItem('user', user_json)
```

**Limitations:**
- ❌ Vulnerable to XSS attacks (any injected script can read token)
- ⚠️ Not cleared on browser crash (manual logout required)
- ✅ Survives page refresh and tab closure

### Recommended for Production (2025 Roadmap)
```typescript
// httpOnly cookies: immune to XSS
Set-Cookie: auth_token=jwt_token; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=900
```

**Migration Path:**
1. **Pilot Phase (Q1 2025):** Keep localStorage, add HTTPS enforcement
2. **Phase 2 (Q2 2025):** Dual-write to both localStorage and httpOnly cookies
3. **Phase 3 (Q3 2025):** Deprecate localStorage, use cookies only

### Transport Security
- ✅ **TLS/HTTPS:** Enforced for all API communications (production)
- ✅ **HSTS:** 31,536,000 seconds (1 year, production only)
- ✅ **Certificate Pinning:** Recommended for mobile clients (not implemented)

---

## CORS Configuration

### Environment-Driven Origins
```python
# Backend configuration (src/bomipay/config.py)
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com

# Parsed into list and applied to FastAPI middleware
cors_allowed_origins_list = ["http://localhost:3000", "https://yourdomain.com"]
```

### Current Allowed Origins (Development)
- `http://localhost:3000` (local dev)
- `http://127.0.0.1:3000` (local dev)

### Production Requirements
- ✅ Must be set via environment variable
- ✅ Must be strict list (no wildcards)
- ✅ Must be HTTPS only
- ✅ Must be specific domains (no *.domain.com)

### CORS Headers Applied
```
Access-Control-Allow-Origin: [configured origin]
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type, X-Request-ID, X-Correlation-ID, X-Paystack-Signature
```

---

## API Security

### Frontend API URL
```typescript
// Frontend (bomipay-website/src/lib/api.ts)
const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'
```

**Configuration Methods:**
1. Environment Variable (Recommended): `NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1`
2. Fallback Default: `http://localhost:8000/api/v1`

### API Versioning
- ✅ All endpoints prefixed with `/api/v1`
- ✅ Backward-compatible versioning strategy
- ⚠️ No deprecation policy documented (implement in Phase 2)

### Request/Response Security
- ✅ Request ID tracking: `X-Request-ID` header
- ✅ Correlation ID: `X-Correlation-ID` header
- ✅ Content-Type enforcement: `application/json` only
- ✅ Request timeout: 30 seconds (frontend axios)

---

## Sensitive Data Handling

### Account Number Masking
**Status:** ⚠️ Not fully implemented (needs Phase 2 deployment)

**Recommended Implementation:**
```typescript
function maskAccountNumber(accountNumber: string): string {
  if (!accountNumber || accountNumber.length < 4) return '••••'
  return `••••${accountNumber.slice(-4)}`
}

// Usage in UI components:
<p>Account: {maskAccountNumber(bankAccount.number)}</p>
// Displays: Account: ••••7890
```

**Display Rules:**
- ✅ Merchant dashboards: Show masked account numbers
- ✅ Reconciliation reports: Show masked account numbers
- ❌ API responses: Full numbers (needed for backend processing)
- ⚠️ Audit logs: Full numbers (for compliance, restricted access)

### Provider Credentials
- ✅ Never logged or printed
- ✅ Stored encrypted in database
- ✅ Encryption key: `PROVIDER_ENCRYPTION_KEY` (base64-encoded, 32-byte)
- ✅ Encryption algorithm: Fernet (symmetric)
- ✅ Key rotation: Quarterly recommended

### Payment Card Data
- ✅ **No cards stored directly** (use payment gateway tokens only)
- ✅ Paystack payment tokens: Stored in database
- ✅ Flutterwave payment tokens: Stored in database
- ✅ Monnify payment tokens: Stored in database
- ✅ Customer PII: Name, email stored with encryption for key fields

---

## Rate Limiting

### Per-Endpoint Configuration
```python
# src/bomipay/middleware/rate_limit.py
Auth Endpoints      (/api/v1/auth/*)    : 10   requests/minute per IP
Webhook Endpoints   (/webhooks/*)       : 100  requests/minute per IP
AI Endpoints        (/api/v1/ai*)       : 20   requests/minute per IP
Default             (all others)        : 200  requests/minute per IP
```

### Implementation Details
- **Limiter:** Sliding-window in-memory (via slowapi)
- **Key:** IP address + endpoint prefix
- **Response:** 429 Too Many Requests with Retry-After header
- **Bypass:** Configurable via `RATE_LIMIT_ENABLED` env var
- **Environment:** Disabled in development/test, active in production/staging

### DDoS Mitigation
- ✅ Configured at application level
- ⚠️ Should also be configured at reverse proxy/WAF level (nginx, cloudflare)
- ⚠️ No distributed rate limiting (Redis-based key sharing not implemented)

---

## Security Headers

### Implemented Headers (src/bomipay/middleware/security.py)
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: <TBD - needs frontend audit>
```

### Development vs. Production
- ✅ HSTS: `31536000` seconds (1 year) in production, configurable
- ✅ CSP: Enabled via `CSP_ENABLED` env var
- ✅ All headers: Configurable via environment

### Recommended Hardening
1. Add `Content-Security-Policy-Report-Only` for monitoring
2. Add `Permissions-Policy` (formerly Feature-Policy)
3. Add `Referrer-Policy: strict-origin-when-cross-origin`

---

## Audit Logging

### What Is Logged
```python
# src/bomipay/services/audit.py
- User login/logout
- Password changes
- Provider connections (Paystack, Flutterwave, Monnify)
- Payment verification events
- Settlement confirmations
- Account updates
- Sensitive API calls
```

### Audit Log Schema
```python
class AuditLog:
    id: UUID
    actor_id: UUID (user who performed action)
    actor_role: str (merchant, admin, etc.)
    event_type: str (login, payment_verified, etc.)
    event_payload: dict (context-specific details)
    source: str (api, webhook, batch, etc.)
    created_at: datetime
    updated_at: datetime
```

### Access Control
- ✅ Merchant isolation: Users only see their own audit logs
- ✅ Admin access: Full audit log visibility
- ✅ Immutability: Logs cannot be modified/deleted
- ⚠️ No encryption (should encrypt sensitive fields in Phase 2)

### Query Endpoint
```
GET /api/v1/audit-logs
Authorization: Bearer <jwt_token>
Parameters: ?page=1&limit=100&event_type=login&start_date=2025-01-01
Response: paginated audit log entries with timestamps
```

### Log Retention
- ✅ Default: 90 days (configurable)
- ⚠️ No automatic archival to cold storage (implement in Phase 2)

---

## Provider Integration Security

### Provider API Keys
- ✅ **Storage:** Encrypted in database per merchant
- ✅ **Encryption:** Fernet symmetric encryption
- ✅ **Key Management:** Master key from environment variable
- ✅ **Rotation:** Manual (web UI provided for merchants)
- ⚠️ **Key Derivation:** Master key is static (should use KMS in production)

### Webhook Verification
- ✅ **Paystack:** Signature verification using `X-Paystack-Signature` header
- ✅ **Flutterwave:** Signature verification using webhook secret
- ✅ **Monnify:** Signature verification using webhook secret
- ✅ **Replay Protection:** Webhook idempotency via nonce/timestamp

### Sensitive Data in Webhooks
- ⚠️ Provider webhooks may contain PII (email, phone, account numbers)
- ⚠️ Webhooks logged for audit purposes (sensitive fields should be redacted)
- ✅ HTTPS enforced for all webhook callbacks

---

## Secrets Management

### Secrets That Must Be Environment Variables
```
SECRET_KEY                    - FastAPI secret, 32+ chars, random
PROVIDER_ENCRYPTION_KEY       - Base64-encoded 32-byte key
CORS_ALLOWED_ORIGINS          - Comma-separated domain list
SENTRY_DSN                    - Sentry error tracking (optional)
OTEL_EXPORTER_OTLP_ENDPOINT  - OpenTelemetry endpoint (optional)
```

### Secrets Never Committed
- ❌ `.env` (only `.env.example`)
- ❌ `.env.production` (only `.env.production.example`)
- ❌ `*.pem`, `*.key` files
- ❌ API tokens, credentials
- ✅ Enforced via `.gitignore` and pre-commit hooks (recommended)

### Secret Scanning
```powershell
# Scan for committed secrets
git log -p -S "sk_live|sk_test|pk_live|password=" --all

# Pre-commit hook to prevent secret commits
# Install: pip install detect-secrets
detect-secrets scan
```

---

## Known Vulnerabilities & Mitigations

### Dependency Vulnerabilities (As of 2026-01-17)

#### Backend (pip-audit)
| Package | Version | CVE | Severity | Fix | Mitigation |
|---------|---------|-----|----------|-----|-----------|
| idna | 3.11 | CVE-2026-45409 | MEDIUM | 3.15 | ⏳ Update pending (no exploitable surface) |
| pip | 26.0.1 | CVE-2026-3219 | LOW | 26.1 | ⏳ Update to 26.1.2 |
| pip | 26.0.1 | CVE-2026-6357 | LOW | 26.1 | ⏳ Update to 26.1.2 |
| starlette | 1.0.0 | PYSEC-2026-161 | MEDIUM | 1.0.1 | ⏳ Update pending |

**Mitigation Strategy:**
- All vulnerabilities are in dependencies, not core logic
- No direct exploitation vector in Bomi Pay usage
- Update as part of quarterly dependency review
- No impact on pilot deployment

#### Frontend (npm audit)
| Package | Issue | Severity | Fix | Mitigation |
|---------|-------|----------|-----|-----------|
| postcss | XSS in CSS stringify | MODERATE | 8.5.10+ | npm audit fix available |
| next | Depends on vulnerable postcss | MODERATE | See above | See above |

**Mitigation Strategy:**
- Run `npm audit fix --force` to update Next.js to v9.3.3
- No impact on current functionality
- Part of standard dependency maintenance

### Application-Level Known Issues

| Issue | Impact | Risk | Timeline |
|-------|--------|------|----------|
| localStorage tokens (XSS vulnerability) | If XSS injected, tokens compromised | MEDIUM | Q2 2025 migration to httpOnly cookies |
| No static secrets scanning in CI/CD | Risk of accidental secret commits | MEDIUM | Q1 2025 add pre-commit hooks |
| Audit logs not encrypted at rest | If DB breached, audit logs readable | LOW | Q3 2025 field-level encryption |
| No key rotation for provider keys | Compromised key affects all past transactions | LOW | Q2 2025 implement KMS + key versioning |
| Rate limiting not distributed (single instance) | Ineffective if multiple API instances | LOW | Q3 2025 Redis-based distributed limiter |
| Payment card data stored (tokens) | PCI scope includes token storage | MEDIUM | Q4 2025 move to payment gateway vault |

---

## Compliance Status

### Current: Non-PCI Compliant
- ❌ Not meeting PCI-DSS Level 1 requirements
- ⚠️ Suitable for **production pilot only**
- ❌ Not audited by external security firm

### Target: PCI-DSS Level 1 (2025)
**Key Requirements to Implement:**
1. ✅ Network segmentation (infrastructure via docker)
2. ⏳ Encryption in transit (TLS, in progress)
3. ⏳ Encryption at rest (database, Q2 2025)
4. ⏳ Access controls (RBAC, partially done)
5. ⏳ Vulnerability scanning (quarterly, to implement)
6. ⏳ Incident response plan (to document)
7. ⏳ Third-party auditing (Q4 2025)

---

## Security Best Practices

### For Developers
1. **Never commit secrets** - use `.env.example` templates
2. **Validate all inputs** - use Pydantic models with strict validation
3. **Log safely** - never log full sensitive fields (use `****` for redaction)
4. **Review dependencies** - run `pip-audit` and `npm audit` weekly
5. **Test security** - include OWASP Top 10 in test suite

### For Operators
1. **Rotate secrets quarterly** - all API keys, encryption keys, tokens
2. **Monitor rate limits** - adjust based on traffic patterns
3. **Review audit logs** - weekly for suspicious activity
4. **Patch dependencies** - update critical/high vulnerabilities within 48 hours
5. **Backup encryption keys** - store in separate secure location

### For Merchants
1. **Use strong passwords** - 12+ characters with mixed case/digits
2. **Store API keys securely** - never in code or emails
3. **Verify webhooks** - implement signature verification
4. **Rotate credentials** - when team members leave
5. **Monitor account** - set up alerts for unusual activity

---

## Testing Security

### Unit Tests
```python
# Test password hashing
def test_password_hashing():
    hashed = hash_password("MySecurePassword123!")
    assert verify_password("MySecurePassword123!", hashed)
    assert not verify_password("WrongPassword", hashed)

# Test JWT generation
def test_jwt_token_generation():
    token = generate_token(user_id="123", expires_in=900)
    payload = decode_token(token)
    assert payload["sub"] == "123"
```

### Integration Tests
```python
# Test rate limiting
def test_rate_limiting():
    for i in range(11):  # Exceed 10 req/min limit
        response = client.post("/api/v1/auth/login", ...)
    assert response.status_code == 429  # Rate limited

# Test CORS
def test_cors_enforcement():
    response = client.get("/api/v1/merchants", 
        headers={"Origin": "https://blocked-domain.com"})
    assert "Access-Control-Allow-Origin" not in response.headers
```

### Security Testing (Manual)
```bash
# Check for XSS vulnerabilities
node node_modules/.bin/eslint --ext .tsx,.ts src/

# Check for SQL injection
# Use SQLMap or manual inspection of query building

# Check SSL/TLS configuration
nmap --script ssl-enum-ciphers -p 443 yourdomain.com

# Check headers
curl -I https://yourdomain.com/api/v1/health
```

---

## Incident Response

### Security Breach Discovery
1. **Isolate**: Stop affected services immediately
2. **Analyze**: Determine what was accessed/modified
3. **Notify**: Inform affected merchants within 2 hours
4. **Remediate**: Apply fixes and deploy patched version
5. **Audit**: Review logs and document findings
6. **Comply**: Report to regulatory bodies if required

### Contact
- **Security Team Email:** security@bomipay.com (to be configured)
- **Incident Hotline:** +234-XXX-XXXX-XXX (to be configured)

---

## References

- [OWASP Top 10 - 2024](https://owasp.org/Top10/)
- [PCI-DSS 4.0 Requirements](https://www.pcisecuritystandards.org/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [CORS Specification](https://fetch.spec.whatwg.org/#http-cors-protocol)
- [Rate Limiting Design](https://stripe.com/blog/rate-limiters)

---

## Document History

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-17 | 1.0 | Initial security posture document for pilot phase |

