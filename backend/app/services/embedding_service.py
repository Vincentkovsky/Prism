from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI

from ..core.config import get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EmbeddingService:
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        chroma_settings = None
        if settings.chroma_server_host:
            self.chroma = chromadb.HttpClient(
                host=settings.chroma_server_host,
                port=settings.chroma_server_port,
                ssl=settings.chroma_server_ssl,
                headers={"Authorization": f"Bearer {settings.chroma_server_api_key}"} if settings.chroma_server_api_key else None,
            )
        else:
            chroma_settings = ChromaSettings()
            self.chroma = chromadb.Client(settings=chroma_settings)
        collection_name = settings.chroma_collection or "documents"
        self.collection = self.chroma.get_or_create_collection(collection_name)
        self._openai_client: Optional[OpenAI] = None
        self.batch_size = 100
        self.log_dir = settings.vector_log_dir
        if self.log_dir:
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)

    def _client(self) -> OpenAI:
        if self._openai_client is None:
            api_key = self.settings.openai_api_key
            self._openai_client = OpenAI(api_key=api_key) if api_key else OpenAI()
        return self._openai_client

    def embed_chunks(self, document_id: str, user_id: str, chunks_file: Path) -> None:
        payload = json.loads(chunks_file.read_text(encoding="utf-8"))
        created_at = _now_iso()
        batch_ids: List[str] = []
        batch_texts: List[str] = []
        batch_metadatas: List[Dict[str, str]] = []

        for idx, item in enumerate(payload):
            batch_ids.append(f"{document_id}_chunk_{idx}")
            batch_texts.append(item["text"])
            metadata: Dict[str, str] = dict(item["metadata"])
            metadata.update(
                {
                    "user_id": user_id,
                    "document_id": document_id,
                    "created_at": created_at,
                }
            )
            batch_metadatas.append(metadata)

        for start in range(0, len(batch_texts), self.batch_size):
            end = start + self.batch_size
            texts = batch_texts[start:end]
            ids = batch_ids[start:end]
            metadatas = batch_metadatas[start:end]

            response = self._client().embeddings.create(
                model="text-embedding-3-large",
                input=texts,
            )
            embeddings = [item.embedding for item in response.data]
            self.collection.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids,
            )
            self._log_batch(document_id, user_id, ids, metadatas)

    def delete_document_vectors(self, document_id: str, user_id: str) -> None:
        self.collection.delete(
            where={
                "document_id": {"$eq": document_id},
                "user_id": {"$eq": user_id},
            }
        )

    def _log_batch(self, document_id: str, user_id: str, ids: List[str], metadatas: List[Dict[str, str]]) -> None:
        if not self.log_dir:
            return
        log_path = Path(self.log_dir) / f"{document_id}.log"
        entry = {
            "document_id": document_id,
            "user_id": user_id,
            "ids": ids,
            "metadatas": metadatas,
            "timestamp": _now_iso(),
        }
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")

