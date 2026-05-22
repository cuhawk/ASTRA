from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import lancedb

EmbedFn = Callable[[list[str]], list[list[float]]]


class VectorStore:
    def __init__(self, path: Path, embed_fn: EmbedFn, dim: int) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(path))
        self._embed_fn = embed_fn
        self._dim = dim

    def upsert(
        self,
        collection: str,
        ids: list[str],
        docs: list[str],
        metas: list[dict] | None = None,
    ) -> int:
        if len(ids) != len(docs):
            raise ValueError(f"ids ({len(ids)}) and docs ({len(docs)}) length mismatch")
        if metas is None:
            metas = [{} for _ in ids]
        if len(metas) != len(ids):
            raise ValueError(f"metas ({len(metas)}) and ids ({len(ids)}) length mismatch")
        if not ids:
            return 0

        vectors = self._embed_fn(docs)
        if len(vectors) != len(docs):
            raise ValueError(
                f"embed_fn returned {len(vectors)} vectors for {len(docs)} docs"
            )
        for i, v in enumerate(vectors):
            if len(v) != self._dim:
                raise ValueError(
                    f"embed_fn vector[{i}] has dim {len(v)}, expected {self._dim}"
                )

        rows = [
            {
                "id": ids[i],
                "doc": docs[i],
                "meta": json.dumps(metas[i]),
                "vector": vectors[i],
            }
            for i in range(len(ids))
        ]

        existing = self._db.list_tables().tables
        if collection not in existing:
            self._db.create_table(collection, data=rows)
            return len(rows)

        tbl = self._db.open_table(collection)
        (
            tbl.merge_insert("id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )
        return len(rows)

    def query(self, collection: str, query_text: str, top_k: int = 5) -> list[dict]:
        if collection not in self._db.list_tables().tables:
            return []
        tbl = self._db.open_table(collection)
        qv = self._embed_fn([query_text])[0]
        if len(qv) != self._dim:
            raise ValueError(
                f"embed_fn query vector has dim {len(qv)}, expected {self._dim}"
            )
        results = tbl.search(qv).limit(top_k).to_list()
        out: list[dict] = []
        for r in results:
            out.append(
                {
                    "id": r["id"],
                    "doc": r["doc"],
                    "meta": json.loads(r["meta"]) if r.get("meta") else {},
                    "score": r.get("_distance"),
                }
            )
        return out

    def list_collections(self) -> list[str]:
        return list(self._db.list_tables().tables)

    def delete_collection(self, collection: str) -> None:
        if collection in self._db.list_tables().tables:
            self._db.drop_table(collection)
