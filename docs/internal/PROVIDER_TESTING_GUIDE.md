# Provider Testing Guide

Internal reference for testing payment provider adapters (Paystack, Flutterwave, Monnify).

---

## Running the Staging Tests

All staging tests use `respx` to mock `httpx` requests. **No real API keys are required.**

```bash
# Run all staging tests (adapter + normalizer + error classification)
pytest tests/test_paystack_adapter_staging.py \
       tests/test_flutterwave_adapter_staging.py \
       tests/test_monnify_adapter_staging.py \
       tests/test_provider_normalize_contract.py \
       tests/test_provider_error_classification.py -v

# Run only tests tagged @pytest.mark.staging
pytest -m staging -v

# Run a single provider's tests
pytest tests/test_paystack_adapter_staging.py -v

# Run with coverage
pytest tests/test_*_adapter_staging.py tests/test_provider_normalize_contract.py \
       tests/test_provider_error_classification.py --cov=bomipay.services -v
```

---

## Running Against Real APIs

Set the following environment variables before running, then use the `--real-api` flag
(or remove `respx.mock` blocks for manual integration testing):

| Variable | Description |
|---|---|
| `PAYSTACK_SECRET_KEY` | Paystack secret key (`sk_test_…` or `sk_live_…`) |
| `FLUTTERWAVE_SECRET_KEY` | Flutterwave secret key (`FLWSECK_TEST-…`) |
| `MONNIFY_API_KEY` | Monnify API key |
| `MONNIFY_SECRET_KEY` | Monnify secret key |

Example real-API smoke test (not part of the automated suite):

```python
import asyncio
from bomipay.services.paystack_adapter_new import PaystackAdapter

async def smoke():
    adapter = PaystackAdapter(api_key=os.environ["PAYSTACK_SECRET_KEY"])
    health = await adapter.get_provider_health()
    print(health)

asyncio.run(smoke())
```

---

## Fixture Files

Response fixtures live in `tests/fixtures/`:

| File | Provider | Notes |
|---|---|---|
| `paystack_responses.py` | Paystack | Uses `"status": "success"` (string) to match adapter check |
| `flutterwave_responses.py` | Flutterwave | Amounts in major units (Naira); status is `"successful"` |
| `monnify_responses.py` | Monnify | `fetch_transactions` uses `"content"` key; status is uppercase (`PAID`, `FAILED`) |

---

## Adding a New Provider

1. **Create the adapter** in `src/bomipay/services/<provider>_adapter_new.py` extending `BaseAsyncProviderAdapter`.

2. **Add fixtures** in `tests/fixtures/<provider>_responses.py` with:
   - `<PROVIDER>_VERIFY_SUCCESS` — successful verify response
   - `<PROVIDER>_LIST_TRANSACTIONS` — paginated list response
   - `<PROVIDER>_RATE_LIMIT_RESPONSE`, `<PROVIDER>_SERVER_ERROR`, `<PROVIDER>_INVALID_KEY`

3. **Create the staging test file** `tests/test_<provider>_adapter_staging.py` following the structure of the existing files. Include:
   - `TestContractVerification` — ≥5 contract shape tests
   - `TestFaultInjection` — timeout, 429, 500, 401, malformed JSON, partial response
   - `TestPagination` — single page and multi-page scenarios

4. **Add normalizer support** in `ProviderNormalizer`:
   - Add `_normalize_<provider>_transaction(raw)` private method
   - Wire it in `normalize_transaction(provider_name, raw)` dispatch

5. **Add error mapping** in `ProviderErrorMapper`:
   - Add `_map_<provider>_error(http_status, message)` method
   - Wire it in `map_error(provider_name, ...)` dispatch

6. **Add normalizer contract tests** to `tests/test_provider_normalize_contract.py`.

---

## Known API Quirks

### Paystack
- **Amount**: returned in **kobo** (integer × 100 vs Naira)
- **Status field type**: Real Paystack API returns `"status": true` (boolean) in the response body, but the adapter compares `!= "success"` (string). Test fixtures use `"status": "success"` to match the adapter's check.
- **Transaction statuses**: `success`, `failed`, `abandoned`, `returned`, `pending`. The normalizer maps `abandoned` and `returned` → `"failed"`.
- **Pagination**: uses `meta.pageCount` and 1-based page numbers.
- **Date params**: uses Unix timestamps (`from`, `to`) for transaction list.

### Flutterwave
- **Amount**: returned in **major units** (Naira, not kobo)
- **Success status**: uses `"successful"` (not `"success"`) in transaction data; outer envelope uses `"success"`.
- **Pagination**: uses `meta.pagination.has_more` boolean.
- **Date params**: ISO 8601 strings (`from`, `to`).

### Monnify
- **Auth**: Basic Auth (`base64(api_key:secret_key)`), unlike Bearer token for Paystack/Flutterwave.
- **Amount**: `transactionAmount` field (integer or float in raw data — normalizer casts to `int`).
- **Status**: uppercase strings (`PAID`, `COMPLETED`, `PENDING`, `FAILED`, `REVERSED`).
- **List endpoint quirk**: `fetch_transactions` returns items under `"content"` key (not `"data"`), with `"hasNext"` boolean at the response root.
- **Pagination**: zero-based page numbers (`pageNo=0`, `pageNo=1`, ...).
- **verify_transaction**: returns data under `"data"` key (normal).

---

## Test Markers

| Marker | Description |
|---|---|
| `@pytest.mark.staging` | Mock-HTTP staging tests (no network required) |

Run only staging tests:
```bash
pytest -m staging -v
```

---

## Dependencies

`respx` is the mock library for `httpx`. It is listed under `[project.optional-dependencies] dev` in `pyproject.toml`. Install dev dependencies with:

```bash
pip install -e ".[dev]"
```
