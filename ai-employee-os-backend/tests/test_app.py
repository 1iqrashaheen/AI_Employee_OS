from app.main import app


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
