from __future__ import annotations

import hashlib

import pytest

from backend.pillars.memory.vectors import VectorStore


def dummy_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        out.append([b / 255.0 for b in h[:8]])
    return out


def wrong_dim_embed(texts: list[str]) -> list[list[float]]:
    return [[0.0] * 4 for _ in texts]


def test_upsert_and_query(tmp_path):
    store = VectorStore(tmp_path / "v.lance", dummy_embed, dim=8)
    ids = [f"d{i}" for i in range(1, 6)]
    docs = [f"document number {i} talks about topic {i}" for i in range(1, 6)]
    written = store.upsert("notes", ids, docs)
    assert written == 5

    hits = store.query("notes", docs[2], top_k=1)
    assert len(hits) == 1
    assert hits[0]["id"] == "d3"
    assert hits[0]["doc"] == docs[2]


def test_upsert_idempotent(tmp_path):
    store = VectorStore(tmp_path / "v.lance", dummy_embed, dim=8)
    store.upsert("c", ["x"], ["first"])
    store.upsert("c", ["x"], ["second"])

    hits = store.query("c", "second", top_k=10)
    assert len(hits) == 1
    assert hits[0]["id"] == "x"
    assert hits[0]["doc"] == "second"


def test_meta_roundtrip(tmp_path):
    store = VectorStore(tmp_path / "v.lance", dummy_embed, dim=8)
    meta = {"path": "a.js", "chunk": 0}
    store.upsert("c", ["m1"], ["hello world"], metas=[meta])

    hits = store.query("c", "hello world", top_k=1)
    assert len(hits) == 1
    assert hits[0]["meta"] == meta


def test_list_and_delete_collection(tmp_path):
    store = VectorStore(tmp_path / "v.lance", dummy_embed, dim=8)
    store.upsert("alpha", ["a"], ["alpha doc"])
    store.upsert("beta", ["b"], ["beta doc"])

    cols = set(store.list_collections())
    assert cols == {"alpha", "beta"}

    store.delete_collection("alpha")
    assert store.list_collections() == ["beta"]


def test_dim_mismatch_raises(tmp_path):
    store = VectorStore(tmp_path / "v.lance", wrong_dim_embed, dim=8)
    with pytest.raises(ValueError):
        store.upsert("c", ["x"], ["doc"])


def test_query_missing_collection_returns_empty(tmp_path):
    store = VectorStore(tmp_path / "v.lance", dummy_embed, dim=8)
    assert store.query("nope", "anything", top_k=5) == []
