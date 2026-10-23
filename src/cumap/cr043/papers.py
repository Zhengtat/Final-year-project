"""CR-043 paper sets. Development uses SciNLP train + dev only (rule 9); the test split is never chosen here."""

from __future__ import annotations

import hashlib

from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019.stage_b import SC_DEV

SEED = "cr043-dev20"


def _order(doc_key: str) -> str:
    return hashlib.sha256(f"{SEED}|{doc_key}".encode()).hexdigest()


def first_set(n_train: int = 14) -> list[tuple[str, str]]:
    """(split, doc_key): the 6 dev papers plus `n_train` train papers in a fixed hash order (seed `cr043-dev20`)."""
    train = sorted((d.doc_key for d in SciNLPAdapter().load_documents("train")), key=_order)
    return [("dev", d) for d in SC_DEV] + [("train", d) for d in train[:n_train]]
