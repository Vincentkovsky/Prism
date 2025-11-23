from __future__ import annotations

from backend.app.services.subscription_service import CREDIT_PRICING


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_list_plans(client):
    resp = client.get("/api/subscription/plans")
    assert resp.status_code == 200
    data = resp.json()
    assert "free" in data
    assert data["free"]["monthly_credits"] == 100


def test_get_subscription_and_usage(client):
    resp = client.get("/api/subscription", headers=_auth_headers("sub-user"))
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["plan"] == "free"
    assert "features" in payload

    usage_resp = client.get("/api/subscription/usage", headers=_auth_headers("sub-user"))
    assert usage_resp.status_code == 200
    usage = usage_resp.json()
    assert usage["plan"] == "free"
    assert usage["remaining_credits"] == usage["monthly_credits"]


def test_checkout_and_webhook_promotes_plan(client):
    checkout_resp = client.post(
        "/api/subscription/checkout",
        json={"plan": "basic"},
        headers=_auth_headers("checkout-user"),
    )
    assert checkout_resp.status_code == 201
    session = checkout_resp.json()
    assert session["plan"] == "basic"
    assert "checkout_url" in session

    webhook_payload = {
        "meta": {"event_name": "subscription_created"},
        "data": {"attributes": {"user_id": "checkout-user", "variant_name": "Pro Plan"}},
    }
    webhook_resp = client.post(
        "/api/subscription/webhook/lemonsqueezy",
        json=webhook_payload,
    )
    assert webhook_resp.status_code == 202
    assert webhook_resp.json()["status"] == "activated"

    subscription_resp = client.get("/api/subscription", headers=_auth_headers("checkout-user"))
    assert subscription_resp.status_code == 200
    assert subscription_resp.json()["plan"] == "pro"


def test_api_keys_require_feature(client):
    resp = client.get("/api/subscription/api-keys", headers=_auth_headers("key-user"))
    assert resp.status_code == 403

    subscription = client.app.state.test_subscription
    subscription.set_user_plan("key-user", "pro")

    create_resp = client.post(
        "/api/subscription/api-keys",
        json={"name": "build"},
        headers=_auth_headers("key-user"),
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert "id" in created
    assert "api_key" in created

    list_resp = client.get("/api/subscription/api-keys", headers=_auth_headers("key-user"))
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "build"


def test_api_key_crud_for_pro_user(client):
    user_id = "pro-user"
    subscription = client.app.state.test_subscription
    subscription.set_user_plan(user_id, "pro")

    create_resp = client.post(
        "/api/subscription/api-keys",
        headers=_auth_headers(user_id),
        json={"name": "CI Key"},
    )
    assert create_resp.status_code == 201
    payload = create_resp.json()
    key_id = payload["id"]
    assert "api_key" in payload

    list_resp = client.get(
        "/api/subscription/api-keys",
        headers=_auth_headers(user_id),
    )
    assert list_resp.status_code == 200
    keys = list_resp.json()
    assert any(key["id"] == key_id for key in keys)

    delete_resp = client.delete(
        f"/api/subscription/api-keys/{key_id}",
        headers=_auth_headers(user_id),
    )
    assert delete_resp.status_code == 204

    list_resp = client.get(
        "/api/subscription/api-keys",
        headers=_auth_headers(user_id),
    )
    assert list_resp.status_code == 200
    assert list_resp.json() == []


def test_credit_consume_and_refund(client):
    subscription = client.app.state.test_subscription
    user_id = "credit-user"

    consumed = subscription.check_and_consume(user_id, "document_upload_pdf")
    assert consumed is True
    usage = subscription.get_usage(user_id)
    assert usage["consumed_credits"] == CREDIT_PRICING["document_upload_pdf"]["credits"]

    subscription.refund_credits(user_id, "document_upload_pdf", reason="unit_test")
    usage_after = subscription.get_usage(user_id)
    assert usage_after["consumed_credits"] == 0

