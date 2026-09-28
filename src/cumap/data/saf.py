"""SAF (Short-Answer-Feedback) dataset ingestion.

Splits: train, validation, test_unseen_answers, test_unseen_questions.
Fields: id (HF row uuid, NOT a question/student id), question, reference_answer,
provided_answer, answer_feedback, verification_feedback, score.

`answer_feedback` is privileged (CLAUDE.md rule 10): only the M4 silver-label
builder may read it. Everything downstream of M4 must load `saf_answers.parquet`
through a view that drops it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from cumap.data.ids import answer_id, question_id

SPLIT_NAMES = ["train", "validation", "test_unseen_answers", "test_unseen_questions"]
HF_DATASET = "Short-Answer-Feedback/saf_communication_networks_english"

PRIVILEGED_COLUMNS = ["answer_feedback"]

_LOOSE_SPLIT_FILE_RE = re.compile(
    r"^(train|validation|test_unseen_answers|test_unseen_questions)-\d+-of-\d+-[0-9a-f]+\.parquet$"
)


def find_loose_split_files(search_dir: Path) -> dict[str, Path]:
    """Find HF-style `<split>-00000-of-00001-<hash>.parquet` files sitting loose in a dir."""
    found: dict[str, Path] = {}
    if not search_dir.exists():
        return found
    for path in search_dir.glob("*.parquet"):
        match = _LOOSE_SPLIT_FILE_RE.match(path.name)
        if match:
            found[match.group(1)] = path
    return found


def download_saf(raw_dir: Path, *, loose_search_dir: Path | None = None) -> dict[str, Path]:
    """Populate raw_dir/<split>.parquet for all four SAF splits.

    Loose HF-export files already present under `loose_search_dir` are copied into
    place instead of re-downloading. Any remaining splits fall back to
    `datasets.load_dataset(HF_DATASET)`.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    loose = find_loose_split_files(loose_search_dir) if loose_search_dir else {}
    out_paths: dict[str, Path] = {}

    for split, src in loose.items():
        dest = raw_dir / f"{split}.parquet"
        if not dest.exists():
            dest.write_bytes(src.read_bytes())
        out_paths[split] = dest

    missing = [s for s in SPLIT_NAMES if s not in out_paths]
    if missing:
        from datasets import load_dataset

        dataset = load_dataset(HF_DATASET)
        for split in missing:
            dest = raw_dir / f"{split}.parquet"
            dataset[split].to_pandas().to_parquet(dest, index=False)
            out_paths[split] = dest

    return out_paths


def load_split(raw_dir: Path, split: str) -> pd.DataFrame:
    df = pd.read_parquet(raw_dir / f"{split}.parquet")
    df["split"] = split
    return df


def load_all_splits(raw_dir: Path) -> pd.DataFrame:
    return pd.concat([load_split(raw_dir, s) for s in SPLIT_NAMES], ignore_index=True)


def add_stable_ids(all_answers: pd.DataFrame) -> pd.DataFrame:
    df = all_answers.copy()
    df["question_id"] = df["question"].map(question_id)
    df["answer_id"] = [
        answer_id(qid, ans) for qid, ans in zip(df["question_id"], df["provided_answer"], strict=True)
    ]
    return df


def build_question_table(all_answers: pd.DataFrame) -> pd.DataFrame:
    """One row per distinct question_id (exact question text), with per-split counts.

    Note: some question_ids are near-duplicate phrasings of the same underlying
    question (cosmetic rewording) — see reports/m1_eda_saf.md for the list found
    in this dataset. They keep separate IDs here for evidence traceability; the
    human picking pilot questions should treat them as one topic.
    """
    rows = []
    for qid, group in all_answers.groupby("question_id"):
        row = {
            "question_id": qid,
            "question": group["question"].iloc[0],
            "reference_answer": group["reference_answer"].iloc[0],
        }
        counts = group["split"].value_counts()
        for split in SPLIT_NAMES:
            row[f"n_{split}"] = int(counts.get(split, 0))
        row["n_total"] = len(group)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("question_id").reset_index(drop=True)


def drop_privileged_columns(df: pd.DataFrame) -> pd.DataFrame:
    """View of an answers table with privileged columns removed (rule 10)."""
    return df.drop(columns=[c for c in PRIVILEGED_COLUMNS if c in df.columns])
