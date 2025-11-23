from __future__ import annotations

import pytest

from backend.app.api.routes import qa


class StubRAGService:
    def query(self, **kwargs):
        return {"answer": "hello", "cached": False, "model_used": kwargs.get("model")}


def stub_enqueue_analysis(document_id, user_id, priority, sku):
    return {"final_report": {"document_id": document_id, "user_id": user_id}}


@pytest.fixture(autouse=True)
def override_dependencies(client):
    app = client.app
    app.dependency_overrides[qa.get_rag_service_dep] = lambda: StubRAGService()
    app.dependency_overrides[qa.get_enqueue_analysis_dep] = lambda: stub_enqueue_analysis
    app.dependency_overrides[qa.get_subscription_service_dep] = lambda: app.state.test_subscription
    yield
    app.dependency_overrides.pop(qa.get_rag_service_dep, None)
    app.dependency_overrides.pop(qa.get_enqueue_analysis_dep, None)
    app.dependency_overrides.pop(qa.get_subscription_service_dep, None)


def test_qa_query_consumes_credits(client):
    token = "qa-user"
    resp = client.post(
        "/api/qa/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"document_id": "doc1", "question": "hi"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["answer"] == "hello"


def test_qa_query_insufficient_credits(client):
    token = "qa-nocredit"
    sub = client.app.state.test_subscription
    ledger = sub._ledger(token)
    ledger.consumed = sub._monthly_quota(ledger.plan)
    resp = client.post(
        "/api/qa/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"document_id": "doc1", "question": "hi"},
    )
    assert resp.status_code == 402


def test_analysis_generate_inline_completion(client):
    token = "qa-analyst"
    resp = client.post(
        "/api/qa/analysis/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"document_id": "doc2"},
    )
    assert resp.status_code == 202
    payload = resp.json()
    assert payload["status"] == "completed"
    assert "report" in payload


def test_analysis_generate_insufficient_credits(client):
    token = "qa-analyst-nocredit"
    sub = client.app.state.test_subscription
    ledger = sub._ledger(token)
    ledger.consumed = sub._monthly_quota(ledger.plan)
    resp = client.post(
        "/api/qa/analysis/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"document_id": "doc2"},
    )
    assert resp.status_code == 402

