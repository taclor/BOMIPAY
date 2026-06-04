"""Real-shape Flutterwave API response fixtures for staging tests.

Flutterwave uses string status "success"/"error" in response bodies and
ISO 8601 dates. Amount fields are in the currency's base unit (e.g. Naira,
not kobo — Flutterwave works in major units unlike Paystack).
"""

FLW_VERIFY_SUCCESS = {
    "status": "success",
    "message": "Transaction fetched successfully",
    "data": {
        "id": 4567890,
        "tx_ref": "flw_ref_abc123",
        "flw_ref": "FLW_REF_001",
        "device_fingerprint": "fp_abc",
        "amount": 5000,  # Naira (major units)
        "currency": "NGN",
        "charged_amount": 5075,
        "app_fee": 75,
        "merchant_fee": 0,
        "processor_response": "Approved",
        "auth_model": "PIN",
        "ip": "::ffff:10.0.0.1",
        "narration": "Test payment",
        "status": "successful",
        "payment_type": "card",
        "created_at": "2024-01-15T10:30:00.000Z",
        "account_id": 12345,
        "customer": {
            "id": 98765,
            "name": "Test User",
            "phone_number": "08000000000",
            "email": "user@example.com",
            "created_at": "2023-06-01T00:00:00.000Z",
        },
        "card": {
            "first_6digits": "412345",
            "last_4digits": "4081",
            "issuer": "VISA",
            "country": "NG",
            "type": "VISA",
            "expiry": "01/26",
        },
        "meta": {},
    },
}

FLW_VERIFY_FAILED = {
    "status": "success",
    "message": "Transaction fetched successfully",
    "data": {
        "id": 4567891,
        "tx_ref": "flw_ref_failed",
        "flw_ref": "FLW_REF_002",
        "amount": 2000,
        "currency": "NGN",
        "charged_amount": 2000,
        "app_fee": 0,
        "processor_response": "Declined",
        "status": "failed",
        "payment_type": "card",
        "created_at": "2024-01-15T11:00:00.000Z",
        "customer": {"id": 98766, "email": "user2@example.com"},
        "meta": {},
    },
}

FLW_VERIFY_PENDING = {
    "status": "success",
    "message": "Transaction fetched successfully",
    "data": {
        "id": 4567892,
        "tx_ref": "flw_ref_pending",
        "flw_ref": "FLW_REF_003",
        "amount": 3000,
        "currency": "NGN",
        "charged_amount": 3000,
        "app_fee": 0,
        "processor_response": "Pending",
        "status": "pending",
        "payment_type": "ussd",
        "created_at": "2024-01-15T12:00:00.000Z",
        "customer": {"id": 98767, "email": "user3@example.com"},
        "meta": {},
    },
}

FLW_LIST_TRANSACTIONS = {
    "status": "success",
    "message": "Transactions fetched",
    "data": [
        {
            "id": 3001,
            "tx_ref": "flw_list_001",
            "flw_ref": "FLW_LIST_001",
            "amount": 1000,
            "currency": "NGN",
            "charged_amount": 1015,
            "app_fee": 15,
            "status": "successful",
            "payment_type": "card",
            "created_at": "2024-01-10T08:00:00.000Z",
            "customer": {"id": 11, "email": "a@example.com"},
            "meta": {},
        },
        {
            "id": 3002,
            "tx_ref": "flw_list_002",
            "flw_ref": "FLW_LIST_002",
            "amount": 2000,
            "currency": "NGN",
            "charged_amount": 2000,
            "app_fee": 0,
            "status": "failed",
            "payment_type": "bank",
            "created_at": "2024-01-11T09:00:00.000Z",
            "customer": {"id": 12, "email": "b@example.com"},
            "meta": {},
        },
        {
            "id": 3003,
            "tx_ref": "flw_list_003",
            "flw_ref": "FLW_LIST_003",
            "amount": 500,
            "currency": "NGN",
            "charged_amount": 500,
            "app_fee": 0,
            "status": "pending",
            "payment_type": "ussd",
            "created_at": "2024-01-12T10:00:00.000Z",
            "customer": {"id": 13, "email": "c@example.com"},
            "meta": {},
        },
    ],
    "meta": {"page_info": {"total": 3, "current_page": 1, "total_pages": 1}, "pagination": {"has_more": False}},
}

FLW_LIST_TRANSACTIONS_PAGE1 = {
    "status": "success",
    "message": "Transactions fetched",
    "data": [
        {
            "id": 4001,
            "tx_ref": "flw_p1_001",
            "flw_ref": "FLW_P1_001",
            "amount": 1500,
            "currency": "NGN",
            "charged_amount": 1523,
            "app_fee": 23,
            "status": "successful",
            "payment_type": "card",
            "created_at": "2024-01-10T08:00:00.000Z",
            "customer": {"id": 21, "email": "d@example.com"},
            "meta": {},
        }
    ],
    "meta": {"pagination": {"has_more": True, "current_page": 1, "total_pages": 2}},
}

FLW_LIST_TRANSACTIONS_PAGE2 = {
    "status": "success",
    "message": "Transactions fetched",
    "data": [
        {
            "id": 4002,
            "tx_ref": "flw_p1_002",
            "flw_ref": "FLW_P1_002",
            "amount": 2500,
            "currency": "NGN",
            "charged_amount": 2538,
            "app_fee": 38,
            "status": "successful",
            "payment_type": "card",
            "created_at": "2024-01-11T08:00:00.000Z",
            "customer": {"id": 22, "email": "e@example.com"},
            "meta": {},
        }
    ],
    "meta": {"pagination": {"has_more": False, "current_page": 2, "total_pages": 2}},
}

# Error response bodies (HTTP status code drives adapter behavior)
FLW_RATE_LIMIT_RESPONSE = {"status": "error", "message": "Rate limit exceeded"}

FLW_SERVER_ERROR = {"status": "error", "message": "Internal server error"}

FLW_INVALID_KEY = {"status": "error", "message": "Invalid authorization key"}

FLW_NOT_FOUND = {"status": "error", "message": "No transaction was found for this id"}
