from app.main import app


def test_openapi_is_available():
    paths = app.openapi()["paths"]

    assert "/api/v1/health" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/customers/{customer_id}/timeline" in paths
    assert "/api/v1/tasks" in paths


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
