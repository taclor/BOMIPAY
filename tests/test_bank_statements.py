"""Tests for Bank Statement Ingestion module."""
import io
import pytest


async def _register_and_login(client, email: str, phone: str, name: str = ""):
    merchant_name = name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "BS User",
            "email": email,
            "phone": phone,
            "password": "BankStmtPass123!",
            "merchant_name": merchant_name,
        },
    )
    assert reg.status_code == 201
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "BankStmtPass123!"},
    )
    tokens = login.json()
    return merchant_id, {"Authorization": f"Bearer {tokens['access_token']}"}


def _make_csv(rows: list[dict]) -> bytes:
    """Build a minimal bank statement CSV from rows of dicts."""
    headers = "date,description,debit,credit,balance,reference\n"
    lines = [headers]
    for r in rows:
        lines.append(
            f"{r.get('date','2024-01-15')},"
            f"{r.get('description','Payment')},"
            f"{r.get('debit','')},"
            f"{r.get('credit','')},"
            f"{r.get('balance','')},"
            f"{r.get('reference','')}\n"
        )
    return "".join(lines).encode("utf-8")


@pytest.mark.asyncio
async def test_csv_import_creates_import_and_entries(client):
    mid, headers = await _register_and_login(
        client, "bs_import@example.com", "+2348003000001"
    )
    csv_data = _make_csv([
        {"date": "2024-01-15", "description": "POS Credit", "credit": "500000", "balance": "500000"},
        {"date": "2024-01-16", "description": "Transfer Out", "debit": "100000", "balance": "400000"},
    ])

    resp = await client.post(
        "/api/v1/bank-statements/import",
        files={"file": ("statement.csv", io.BytesIO(csv_data), "text/csv")},
        data={"merchant_id": mid, "currency": "NGN"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] in ("completed", "processing", "failed")
    import_id = data["id"]

    # List imports
    list_resp = await client.get(
        f"/api/v1/bank-statements/imports?merchant_id={mid}", headers=headers
    )
    assert list_resp.status_code == 200
    assert any(i["id"] == import_id for i in list_resp.json())

    # Get single import
    get_resp = await client.get(
        f"/api/v1/bank-statements/imports/{import_id}", headers=headers
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == import_id


@pytest.mark.asyncio
async def test_csv_import_entries_accessible(client):
    mid, headers = await _register_and_login(
        client, "bs_entries@example.com", "+2348003000002"
    )
    csv_data = _make_csv([
        {"date": "2024-02-01", "description": "USSD Credit", "credit": "200000", "balance": "200000"},
    ])
    resp = await client.post(
        "/api/v1/bank-statements/import",
        files={"file": ("stmt2.csv", io.BytesIO(csv_data), "text/csv")},
        data={"merchant_id": mid},
        headers=headers,
    )
    import_id = resp.json()["id"]

    entries_resp = await client.get(
        f"/api/v1/bank-statements/imports/{import_id}/entries",
        headers=headers,
    )
    assert entries_resp.status_code == 200
    assert isinstance(entries_resp.json(), list)


@pytest.mark.asyncio
async def test_duplicate_csv_import_is_idempotent(client):
    """Uploading the same CSV twice should not double-count entries."""
    mid, headers = await _register_and_login(
        client, "bs_dedup@example.com", "+2348003000003"
    )
    csv_data = _make_csv([
        {"date": "2024-03-01", "description": "Dedup Test", "credit": "999999", "reference": "REF-DEDUP-01"},
    ])

    resp1 = await client.post(
        "/api/v1/bank-statements/import",
        files={"file": ("dedup.csv", io.BytesIO(csv_data), "text/csv")},
        data={"merchant_id": mid},
        headers=headers,
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        "/api/v1/bank-statements/import",
        files={"file": ("dedup.csv", io.BytesIO(csv_data), "text/csv")},
        data={"merchant_id": mid},
        headers=headers,
    )
    # Second import should succeed but not create duplicate entries
    assert resp2.status_code == 201

    entries_resp = await client.get(
        f"/api/v1/bank-statements/entries?merchant_id={mid}", headers=headers
    )
    assert entries_resp.status_code == 200
    entries = entries_resp.json()
    refs = [e.get("reference") for e in entries if e.get("reference") == "REF-DEDUP-01"]
    assert len(refs) == 1, "Duplicate entries must not be created"


@pytest.mark.asyncio
async def test_invalid_file_type_rejected(client):
    mid, headers = await _register_and_login(
        client, "bs_invalid@example.com", "+2348003000004"
    )
    resp = await client.post(
        "/api/v1/bank-statements/import",
        files={"file": ("bad.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"merchant_id": mid},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bank_statement_tenant_isolation(client):
    mid_a, headers_a = await _register_and_login(
        client, "bs_tenant_a@example.com", "+2348003000005", "BS Tenant A"
    )
    mid_b, _, = await _register_and_login(
        client, "bs_tenant_b@example.com", "+2348003000006", "BS Tenant B"
    )
    # Login as B to get headers
    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "bs_tenant_b@example.com", "password": "BankStmtPass123!"},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    csv_data = _make_csv([
        {"date": "2024-04-01", "description": "Tenant A entry", "credit": "100000"},
    ])
    import_resp = await client.post(
        "/api/v1/bank-statements/import",
        files={"file": ("tenant_a.csv", io.BytesIO(csv_data), "text/csv")},
        data={"merchant_id": mid_a},
        headers=headers_a,
    )
    import_id = import_resp.json()["id"]

    # Merchant B should be denied access
    resp = await client.get(
        f"/api/v1/bank-statements/imports/{import_id}", headers=headers_b
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bank_statements_require_auth(client):
    resp = await client.get("/api/v1/bank-statements/imports")
    assert resp.status_code == 401
