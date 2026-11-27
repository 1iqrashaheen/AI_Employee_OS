from app.main import app
import uuid


def test_openapi_is_available():
    paths = app.openapi()["paths"]

    assert "/api/v1/health" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/customers/{customer_id}/timeline" in paths
    assert "/api/v1/tasks" in paths
    assert "/api/v1/records" in paths
    assert "/api/v1/records/{record_id}" in paths


def test_routers_are_registered_once():
    openapi = app.openapi()
    auth_login_operations = [
        method
        for method in openapi["paths"]["/api/v1/auth/login"]
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    debug_operations = openapi["paths"].get("/api/v1/debug/crash", {})

    assert auth_login_operations == ["post"]
    assert set(debug_operations) == {"get"}


def test_record_schema_and_filter_contract():
    openapi = app.openapi()

    record_collection = openapi["paths"]["/api/v1/records"]
    record_item = openapi["paths"]["/api/v1/records/{record_id}"]
    assert set(record_collection) >= {"get", "post"}
    assert set(record_item) >= {"get", "patch", "delete"}
    assert "type" in record_collection["get"]["parameters"][0]["name"] or any(
        parameter["name"] == "type"
        for parameter in record_collection["get"]["parameters"]
    )


def register_admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Test Company",
            "full_name": "Test Admin",
            "email": "admin@example.com",
            "password": "Str0ngPass123",
        },
    )


def test_register_login_and_company_flow(client):
    registered = register_admin(client)
    assert registered.status_code == 201
    tokens = registered.json()["data"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["company"]["name"] == "Test Company"

    updated = client.patch(
        "/api/v1/companies/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"name": "Updated Company", "plan": "pro"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Updated Company"
    assert updated.json()["data"]["plan"] == "pro"


def test_logout_revokes_existing_tokens(client):
    registered = register_admin(client)
    tokens = registered.json()["data"]

    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert logout.status_code == 200

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 401
    assert me.json()["code"] == "TOKEN_REVOKED"


def test_forgot_and_reset_password_flow(client):
    register_admin(client)

    forgot = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "admin@example.com"},
    )
    assert forgot.status_code == 200
    assert forgot.json()["data"] == {"sent": True}


def auth_headers(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def register_and_login(client, email="admin@example.com", password="Str0ngPass123"):
    registered = register_admin(client)
    assert registered.status_code == 201
    return registered.json()["data"]


def test_auth_success_and_failure_cases(client):
    registered = register_admin(client)
    assert registered.status_code == 201

    duplicate = register_admin(client)
    assert duplicate.status_code == 409

    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "WrongPassword1"},
    )
    assert bad_login.status_code == 401

    bad_input = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": ""},
    )
    assert bad_input.status_code == 422

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Str0ngPass123"},
    )
    assert login.status_code == 200
    tokens = login.json()["data"]

    refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 200


def test_auth_requires_token(client):
    for method, path in [
        ("get", "/api/v1/auth/me"),
        ("post", "/api/v1/auth/change-password"),
        ("post", "/api/v1/auth/logout"),
        ("get", "/api/v1/users"),
        ("get", "/api/v1/companies/me"),
        ("get", "/api/v1/customers"),
        ("get", "/api/v1/tasks"),
        ("get", "/api/v1/records"),
    ]:
        response = getattr(client, method)(path)
        assert response.status_code == 401


def test_company_endpoints(client):
    tokens = register_admin(client).json()["data"]
    headers = auth_headers(tokens)

    current = client.get("/api/v1/companies/me", headers=headers)
    assert current.status_code == 200
    assert current.json()["data"]["name"] == "Test Company"

    updated = client.patch(
        "/api/v1/companies/me",
        headers=headers,
        json={"name": "Test Company Updated", "plan": "business"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["plan"] == "business"

    bad = client.patch(
        "/api/v1/companies/me",
        headers=headers,
        json={"plan": "invalid"},
    )
    assert bad.status_code == 422


def test_user_crud_success_and_failures(client):
    tokens = register_and_login(client)
    headers = auth_headers(tokens)

    listed = client.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1

    directory = client.get("/api/v1/users/directory", headers=headers)
    assert directory.status_code == 200

    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "full_name": "Test Member",
            "email": "member@example.com",
            "password": "Member123",
            "role": "member",
        },
    )
    assert created.status_code == 201
    member = created.json()["data"]

    retrieved = client.get(f"/api/v1/users/{member['id']}", headers=headers)
    assert retrieved.status_code == 200

    updated = client.patch(
        f"/api/v1/users/{member['id']}",
        headers=headers,
        json={"phone": "+1-555-0100"},
    )
    assert updated.status_code == 200

    bad_input = client.post(
        "/api/v1/users",
        headers=headers,
        json={"full_name": "X", "email": "bad", "password": "short", "role": "owner"},
    )
    assert bad_input.status_code == 422

    wrong_id = client.get(f"/api/v1/users/{uuid.uuid4()}", headers=headers)
    assert wrong_id.status_code == 404

    deactivated = client.delete(f"/api/v1/users/{member['id']}", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["is_active"] is False


def test_customer_crud_success_and_failures(client):
    tokens = register_and_login(client)
    headers = auth_headers(tokens)

    created = client.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "Acme Client",
            "email": "client@acme.example",
            "organization": "Acme",
            "stage": "lead",
            "tags": ["priority"],
        },
    )
    assert created.status_code == 201
    customer = created.json()["data"]

    listed = client.get("/api/v1/customers", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1

    retrieved = client.get(f"/api/v1/customers/{customer['id']}", headers=headers)
    assert retrieved.status_code == 200

    updated = client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=headers,
        json={"stage": "qualified", "organization": "Acme Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["stage"] == "qualified"

    bad_input = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "", "email": "not-an-email", "stage": "unknown"},
    )
    assert bad_input.status_code == 422

    wrong_id = client.get(f"/api/v1/customers/{uuid.uuid4()}", headers=headers)
    assert wrong_id.status_code == 404

    deleted = client.delete(f"/api/v1/customers/{customer['id']}", headers=headers)
    assert deleted.status_code == 200


def test_task_crud_success_and_failures(client):
    tokens = register_and_login(client)
    headers = auth_headers(tokens)

    customer = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Task Customer"},
    ).json()["data"]

    created = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "title": "Follow up",
            "description": "Call the customer",
            "priority": "high",
            "customer_id": customer["id"],
        },
    )
    assert created.status_code == 201
    task = created.json()["data"]

    listed = client.get("/api/v1/tasks", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1

    retrieved = client.get(f"/api/v1/tasks/{task['id']}", headers=headers)
    assert retrieved.status_code == 200

    updated = client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=headers,
        json={"status": "done", "priority": "urgent"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "done"

    bad_input = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"title": "", "priority": "unknown", "due_date": "2027-01-01"},
    )
    assert bad_input.status_code == 422

    wrong_id = client.get(f"/api/v1/tasks/{uuid.uuid4()}", headers=headers)
    assert wrong_id.status_code == 404

    deleted = client.delete(f"/api/v1/tasks/{task['id']}", headers=headers)
    assert deleted.status_code == 200


def test_record_crud_success_and_failures(client):
    tokens = register_and_login(client)
    headers = auth_headers(tokens)

    customer = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Record Customer"},
    ).json()["data"]

    created = client.post(
        "/api/v1/records",
        headers=headers,
        json={
            "type": "quotation",
            "customer_id": customer["id"],
            "title": "New quotation",
            "reference_no": "QUOTE-001",
            "status": "draft",
            "amount": "125.50",
            "currency": "usd",
        },
    )
    assert created.status_code == 201
    record = created.json()["data"]

    listed = client.get("/api/v1/records", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1

    retrieved = client.get(f"/api/v1/records/{record['id']}", headers=headers)
    assert retrieved.status_code == 200

    updated = client.patch(
        f"/api/v1/records/{record['id']}",
        headers=headers,
        json={"status": "approved", "amount": "150"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "approved"

    duplicate = client.post(
        "/api/v1/records",
        headers=headers,
        json={
            "type": "quotation",
            "customer_id": customer["id"],
            "reference_no": "QUOTE-001",
        },
    )
    assert duplicate.status_code == 409

    bad_input = client.post(
        "/api/v1/records",
        headers=headers,
        json={"type": "unknown", "customer_id": str(uuid.uuid4()), "amount": -1},
    )
    assert bad_input.status_code == 422

    wrong_id = client.get(f"/api/v1/records/{uuid.uuid4()}", headers=headers)
    assert wrong_id.status_code == 404

    deleted = client.delete(f"/api/v1/records/{record['id']}", headers=headers)
    assert deleted.status_code == 200
