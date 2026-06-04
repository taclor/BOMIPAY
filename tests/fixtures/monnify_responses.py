"""Real-shape Monnify API response fixtures for staging tests.

Monnify differences from other providers:
- Uses Basic Auth (base64 of api_key:secret_key)
- fetch_transactions returns "content" (not "data") + "hasNext" pagination
- verify_transaction still returns "data"
- Status values are uppercase: PAID, COMPLETED, PENDING, FAILED
- Amount is in Naira (major units), not kobo
- References are "transactionReference" field
"""

MONNIFY_VERIFY_SUCCESS = {
    "status": "success",
    "message": "success",
    "data": {
        "transactionReference": "MNFY|20240115103000|001",
        "paymentReference": "ref_monnify_001",
        "amountPaid": 5000.0,
        "totalPayable": 5000.0,
        "transactionAmount": 5000,
        "currency": "NGN",
        "paymentStatus": "PAID",
        "transactionDate": "2024-01-15T10:30:00.000+00:00",
        "createdOn": "2024-01-15T10:28:00.000+00:00",
        "paymentMethod": "CARD",
        "customerEmail": "user@example.com",
        "customerName": "Test User",
        "settlementAmount": 4900.0,
        "metaData": {},
    },
}

MONNIFY_VERIFY_COMPLETED = {
    "status": "success",
    "message": "success",
    "data": {
        "transactionReference": "MNFY|20240115110000|002",
        "paymentReference": "ref_monnify_002",
        "amountPaid": 10000.0,
        "totalPayable": 10000.0,
        "transactionAmount": 10000,
        "currency": "NGN",
        "paymentStatus": "COMPLETED",
        "transactionDate": "2024-01-15T11:00:00.000+00:00",
        "createdOn": "2024-01-15T10:58:00.000+00:00",
        "paymentMethod": "ACCOUNT_TRANSFER",
        "customerEmail": "user2@example.com",
        "customerName": "Test User 2",
        "settlementAmount": 9800.0,
        "metaData": {},
    },
}

MONNIFY_VERIFY_PENDING = {
    "status": "success",
    "message": "success",
    "data": {
        "transactionReference": "MNFY|20240115120000|003",
        "paymentReference": "ref_monnify_003",
        "amountPaid": 0.0,
        "totalPayable": 3000.0,
        "transactionAmount": 3000,
        "currency": "NGN",
        "paymentStatus": "PENDING",
        "transactionDate": None,
        "createdOn": "2024-01-15T12:00:00.000+00:00",
        "paymentMethod": "USSD",
        "customerEmail": "user3@example.com",
        "customerName": "Test User 3",
        "settlementAmount": 0.0,
        "metaData": {},
    },
}

MONNIFY_VERIFY_FAILED = {
    "status": "success",
    "message": "success",
    "data": {
        "transactionReference": "MNFY|20240115130000|004",
        "paymentReference": "ref_monnify_004",
        "amountPaid": 0.0,
        "totalPayable": 2000.0,
        "transactionAmount": 2000,
        "currency": "NGN",
        "paymentStatus": "FAILED",
        "transactionDate": None,
        "createdOn": "2024-01-15T13:00:00.000+00:00",
        "paymentMethod": "CARD",
        "customerEmail": "user4@example.com",
        "customerName": "Test User 4",
        "settlementAmount": 0.0,
        "metaData": {},
    },
}

# fetch_transactions returns "content" (not "data") — Monnify API quirk
MONNIFY_LIST_TRANSACTIONS = {
    "status": "success",
    "message": "success",
    "content": [
        {
            "transactionReference": "MNFY|LIST|001",
            "paymentReference": "ref_list_001",
            "transactionAmount": 5000,
            "currency": "NGN",
            "paymentStatus": "PAID",
            "createdOn": "2024-01-10T08:00:00.000+00:00",
            "transactionDate": "2024-01-10T08:01:00.000+00:00",
            "paymentMethod": "CARD",
            "customerEmail": "a@example.com",
            "metaData": {},
        },
        {
            "transactionReference": "MNFY|LIST|002",
            "paymentReference": "ref_list_002",
            "transactionAmount": 2000,
            "currency": "NGN",
            "paymentStatus": "FAILED",
            "createdOn": "2024-01-11T09:00:00.000+00:00",
            "transactionDate": None,
            "paymentMethod": "CARD",
            "customerEmail": "b@example.com",
            "metaData": {},
        },
        {
            "transactionReference": "MNFY|LIST|003",
            "paymentReference": "ref_list_003",
            "transactionAmount": 7500,
            "currency": "NGN",
            "paymentStatus": "PENDING",
            "createdOn": "2024-01-12T10:00:00.000+00:00",
            "transactionDate": None,
            "paymentMethod": "USSD",
            "customerEmail": "c@example.com",
            "metaData": {},
        },
    ],
    "hasNext": False,
    "totalRecords": 3,
    "pageNo": 0,
    "pageSize": 100,
}

MONNIFY_LIST_TRANSACTIONS_PAGE0 = {
    "status": "success",
    "message": "success",
    "content": [
        {
            "transactionReference": "MNFY|PG|001",
            "paymentReference": "ref_pg_001",
            "transactionAmount": 8000,
            "currency": "NGN",
            "paymentStatus": "PAID",
            "createdOn": "2024-01-10T08:00:00.000+00:00",
            "transactionDate": "2024-01-10T08:01:00.000+00:00",
            "paymentMethod": "CARD",
            "customerEmail": "d@example.com",
            "metaData": {},
        }
    ],
    "hasNext": True,
    "totalRecords": 2,
    "pageNo": 0,
    "pageSize": 1,
}

MONNIFY_LIST_TRANSACTIONS_PAGE1 = {
    "status": "success",
    "message": "success",
    "content": [
        {
            "transactionReference": "MNFY|PG|002",
            "paymentReference": "ref_pg_002",
            "transactionAmount": 12000,
            "currency": "NGN",
            "paymentStatus": "COMPLETED",
            "createdOn": "2024-01-11T08:00:00.000+00:00",
            "transactionDate": "2024-01-11T08:01:00.000+00:00",
            "paymentMethod": "ACCOUNT_TRANSFER",
            "customerEmail": "e@example.com",
            "metaData": {},
        }
    ],
    "hasNext": False,
    "totalRecords": 2,
    "pageNo": 1,
    "pageSize": 1,
}

# Error response bodies (HTTP status code drives adapter behavior)
MONNIFY_RATE_LIMIT_RESPONSE = {"status": "error", "message": "Rate limit exceeded"}

MONNIFY_SERVER_ERROR = {"status": "error", "message": "Internal server error"}

MONNIFY_INVALID_KEY = {"responseMessage": "Invalid API credentials", "responseCode": "99"}

MONNIFY_NOT_FOUND = {"status": "error", "message": "Transaction not found"}
