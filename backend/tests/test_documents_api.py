from __future__ import annotations

import io

from backend.app.tasks import document_tasks


def _upload_pdf(client, token: str) -> str:
    file_content = b"%PDF-1.4\n1 0 obj << /Type /Catalog >>\n"
    files = {"file": ("sample.pdf", io.BytesIO(file_content), "application/pdf")}
    response = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert response.status_code == 201
    return response.json()["document_id"]


def test_upload_document(client):
    token = "user-test"
    document_id = _upload_pdf(client, token)

    list_resp = client.get(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    documents = list_resp.json()
    assert len(documents) == 1
    assert documents[0]["id"] == document_id


def test_delete_document(client):
    token = "user-delete"
    document_id = _upload_pdf(client, token)

    delete_resp = client.delete(
        f"/api/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 204

    list_resp = client.get(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    documents = list_resp.json()
    assert documents == []

    embedder = client.app.state.test_embedder
    assert (document_id, token) in embedder.deleted


def test_upload_document_requires_credits(client):
    token = "user-nocredit"
    service = client.app.state.test_service
    ledger = service.subscription._ledger(token)  # type: ignore[attr-defined]
    ledger.consumed = service.subscription._monthly_quota(ledger.plan)  # type: ignore[attr-defined]

    file_content = b"%PDF-1.4\n1 0 obj << /Type /Catalog >>\n"
    files = {"file": ("sample.pdf", io.BytesIO(file_content), "application/pdf")}
    response = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert response.status_code == 402


def test_get_document_status(client):
    token = "status-user"
    document_id = _upload_pdf(client, token)

    resp = client.get(
        f"/api/documents/{document_id}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["document_id"] == document_id
    assert payload["status"] == "completed"


def test_upload_document_refund_once_on_inline_failure(client, monkeypatch):
    token = "inline-fail-user"
    client.app.state.test_service.settings.document_pipeline_enabled = True  # type: ignore[attr-defined]

    def failing_embed(*args, **kwargs):
        raise RuntimeError("embed failed")

    monkeypatch.setattr(document_tasks.EmbeddingService, "embed_chunks", failing_embed)

    file_content = b"%PDF-1.4\n1 0 obj << /Type /Catalog >>\n"
    files = {"file": ("sample.pdf", io.BytesIO(file_content), "application/pdf")}
    response = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert response.status_code == 500

    subscription = client.app.state.test_subscription
    ledger = subscription._ledger(token)  # type: ignore[attr-defined]
    refunds = [
        entry
        for entry in ledger.history
        if entry.get("action") == "refund" and entry.get("sku") == "document_upload_pdf"
    ]
    assert len(refunds) == 1

