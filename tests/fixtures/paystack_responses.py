"""Real-shape Paystack API response fixtures for staging tests.

Note: The adapter's _request_with_retry checks response.get("status") against
the string "success". Paystack's real API returns boolean true, but these fixtures
use the string form to match the adapter's comparison logic.
"""

PAYSTACK_VERIFY_SUCCESS = {
    "status": "success",
    "message": "Verification successful",
    "data": {
        "id": 1234567,
        "reference": "ref_abc123",
        "status": "success",
        "amount": 500000,  # kobo
        "currency": "NGN",
        "paid_at": "2024-01-15T10:30:00.000Z",
        "created_at": "2024-01-15T10:28:00.000Z",
        "channel": "card",
        "customer": {"email": "user@example.com"},
        "fees": 7500,
        "gateway_response": "Successful",
        "authorization": {"card_type": "visa", "last4": "4081", "bank": "TEST BANK"},
        "metadata": {},
    },
}

PAYSTACK_VERIFY_FAILED = {
    "status": "success",
    "message": "Verification successful",
    "data": {
        "id": 1234568,
        "reference": "ref_failed",
        "status": "failed",
        "amount": 200000,
        "currency": "NGN",
        "paid_at": None,
        "created_at": "2024-01-15T11:00:00.000Z",
        "channel": "card",
        "customer": {"email": "user2@example.com"},
        "fees": 0,
        "gateway_response": "Declined",
        "authorization": {},
        "metadata": {},
    },
}

PAYSTACK_VERIFY_ABANDONED = {
    "status": "success",
    "message": "Verification successful",
    "data": {
        "id": 1234569,
        "reference": "ref_abandoned",
        "status": "abandoned",
        "amount": 300000,
        "currency": "NGN",
        "paid_at": None,
        "created_at": "2024-01-15T12:00:00.000Z",
        "channel": "card",
        "customer": {"email": "user3@example.com"},
        "fees": 0,
        "gateway_response": "",
        "authorization": {},
        "metadata": {},
    },
}

PAYSTACK_VERIFY_PENDING = {
    "status": "success",
    "message": "Verification successful",
    "data": {
        "id": 1234570,
        "reference": "ref_pending",
        "status": "pending",
        "amount": 150000,
        "currency": "NGN",
        "paid_at": None,
        "created_at": "2024-01-15T13:00:00.000Z",
        "channel": "mobile_money",
        "customer": {"email": "user4@example.com"},
        "fees": 0,
        "gateway_response": "",
        "authorization": {},
        "metadata": {},
    },
}

PAYSTACK_LIST_TRANSACTIONS = {
    "status": "success",
    "message": "Transactions retrieved",
    "data": [
        {
            "id": 1001,
            "reference": "ref_001",
            "status": "success",
            "amount": 100000,
            "currency": "NGN",
            "paid_at": "2024-01-10T08:00:00.000Z",
            "created_at": "2024-01-10T07:59:00.000Z",
            "channel": "card",
            "customer": {"email": "a@example.com"},
            "fees": 1500,
            "metadata": {},
        },
        {
            "id": 1002,
            "reference": "ref_002",
            "status": "failed",
            "amount": 200000,
            "currency": "NGN",
            "paid_at": None,
            "created_at": "2024-01-11T09:00:00.000Z",
            "channel": "bank",
            "customer": {"email": "b@example.com"},
            "fees": 0,
            "metadata": {},
        },
        {
            "id": 1003,
            "reference": "ref_003",
            "status": "abandoned",
            "amount": 50000,
            "currency": "NGN",
            "paid_at": None,
            "created_at": "2024-01-12T10:00:00.000Z",
            "channel": "ussd",
            "customer": {"email": "c@example.com"},
            "fees": 0,
            "metadata": {},
        },
    ],
    "meta": {"total": 3, "skipped": 0, "perPage": 50, "page": 1, "pageCount": 1},
}

PAYSTACK_LIST_TRANSACTIONS_PAGE1 = {
    "status": "success",
    "message": "Transactions retrieved",
    "data": [
        {
            "id": 2001,
            "reference": "ref_p1_001",
            "status": "success",
            "amount": 150000,
            "currency": "NGN",
            "paid_at": "2024-01-10T08:00:00.000Z",
            "created_at": "2024-01-10T07:59:00.000Z",
            "channel": "card",
            "customer": {"email": "d@example.com"},
            "fees": 2250,
            "metadata": {},
        }
    ],
    "meta": {"total": 2, "skipped": 0, "perPage": 1, "page": 1, "pageCount": 2},
}

PAYSTACK_LIST_TRANSACTIONS_PAGE2 = {
    "status": "success",
    "message": "Transactions retrieved",
    "data": [
        {
            "id": 2002,
            "reference": "ref_p1_002",
            "status": "success",
            "amount": 250000,
            "currency": "NGN",
            "paid_at": "2024-01-11T08:00:00.000Z",
            "created_at": "2024-01-11T07:59:00.000Z",
            "channel": "card",
            "customer": {"email": "e@example.com"},
            "fees": 3750,
            "metadata": {},
        }
    ],
    "meta": {"total": 2, "skipped": 0, "perPage": 1, "page": 2, "pageCount": 2},
}

# Error response bodies (HTTP status codes drive the adapter behavior)
PAYSTACK_RATE_LIMIT_RESPONSE = {"status": False, "message": "Rate limit exceeded"}

PAYSTACK_SERVER_ERROR = {"status": False, "message": "Internal server error"}

PAYSTACK_INVALID_KEY = {"status": False, "message": "Invalid key"}

PAYSTACK_NOT_FOUND = {"status": False, "message": "Transaction not found"}
