from __future__ import annotations

import sqlite3

import numpy as np
from usearch.index import Index

from tokenguard.store.repository import iter_chunks_with_embeddings

_ANN_THRESHOLD = 200


def _blob_to_vec(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def build_ann_index(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None = None,
) -> tuple[Index, dict[int, sqlite3.Row]] | None:
    rows = iter_chunks_with_embeddings(conn, thread_id=thread_id)
    if len(rows) < _ANN_THRESHOLD:
        return None

    ndim = 0
    vectors: list[np.ndarray] = []
    label_map: dict[int, sqlite3.Row] = {}

    for i, row in enumerate(rows):
        blob = row["embedding"]
        if blob is None:
            continue
        v = _blob_to_vec(bytes(blob))
        if ndim == 0:
            ndim = int(v.shape[0])
        vectors.append(v)
        label_map[i] = row

    if not vectors:
        return None

    idx = Index(ndim=ndim, metric="cos")
    keys = np.arange(len(vectors), dtype=np.int64)
    matrix = np.stack(vectors, axis=0).astype(np.float32)
    idx.add(keys, matrix)
    return idx, label_map


def top_k_chunks(
    conn: sqlite3.Connection,
    query_embedding: list[float],
    *,
    k: int,
    thread_id: str | None = None,
    ann_index: tuple[Index, dict[int, sqlite3.Row]] | None = None,
) -> list[tuple[float, sqlite3.Row]]:
    if ann_index is not None:
        idx, label_map = ann_index
        q = np.array(query_embedding, dtype=np.float32)
        matches = idx.search(q, k)
        scored: list[tuple[float, sqlite3.Row]] = []
        for key, dist in zip(matches.keys, matches.distances):
            row = label_map.get(int(key))
            if row is None:
                continue
            sim = float(1.0 - dist)
            scored.append((sim, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    q = np.array(query_embedding, dtype=np.float32)
    qn = np.linalg.norm(q)
    if qn == 0:
        return []
    q = q / qn
    rows = iter_chunks_with_embeddings(conn, thread_id=thread_id)
    scored = []
    for row in rows:
        blob = row["embedding"]
        if blob is None:
            continue
        v = _blob_to_vec(bytes(blob))
        vn = np.linalg.norm(v)
        if vn == 0:
            continue
        sim = float(np.dot(q, v / vn))
        scored.append((sim, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:k]
