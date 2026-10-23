"""CR-015: model DRAFT of the exhaustive concept annotation for the pilot sections (owner reviews it before it is gold).

Rule 2: the draft is written to `data/interim/suggestions/`, never to `data/gold/`. The model sees only section sentences and the guide, never any system output.
    uv run python -m cumap.cr015.gold_draft sentences            # $0: sentence files for the pilot sections
    uv run python -m cumap.cr015.gold_draft draft --dry-run
    uv run python -m cumap.cr015.gold_draft draft --max-usd 3"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Literal

import yaml

from cumap.concepts_v4.schema import NODE_TYPES, _Strict

ROOT = Path(".")
CHK = ROOT / "data/interim/checks/cr015"
SUG = ROOT / "data/interim/suggestions"
MAN = yaml.safe_load((ROOT / "configs/cr015_manifest.yaml").read_text())
NodeTypeL = Literal[*NODE_TYPES]
BATCH = 20


class MentionDraftLLM(_Strict):
    span_text: str
    occurrence: int
    concept_name: str
    node_type: NodeTypeL
    nested_valid: bool


class SentenceDraftLLM(_Strict):
    sentence_id: str
    mentions: list[MentionDraftLLM]


class DraftBatchLLM(_Strict):
    sentences: list[SentenceDraftLLM]


def section_row(sid: str) -> dict:
    for line in (ROOT / "data/interim/textbook_sections.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["section_id"] == sid:
            return r
    raise KeyError(sid)


def make_sentences(sections: list[str]) -> list[tuple]:
    import spacy

    nlp = spacy.load("en_core_web_sm")
    rows = []
    for sid in sections:
        text = section_row(sid)["text"]
        for i, s in enumerate(nlp(text).sents):
            raw = text[s.start_char : s.end_char]
            lead = len(raw) - len(raw.lstrip())
            body = re.sub(r"\s", " ", raw.strip())
            if not body:
                continue
            a = s.start_char + lead
            rows.append((f"{sid}_s{i:04d}", sid, a, a + len(body), body))
    return rows


def write_sentences(sections: list[str], stem: str) -> list[tuple]:
    rows = make_sentences(sections)
    CHK.mkdir(parents=True, exist_ok=True)
    with (CHK / f"{stem}_sentences.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sentence_id", "section_id", "char_start", "char_end", "sentence_text"])
        w.writerows(rows)
    lines = []
    cur = None
    for sid_, sec, _a, _b, body in rows:
        if sec != cur:
            cur = sec
            lines.append(
                f"=== SECTION {sec}: {' > '.join(section_row(sec)['heading_path'] or [])} ==="
            )
        lines.append(f"[{sid_}] {body}")
    (CHK / f"{stem}_text.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (CHK / f"{stem}_blind.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                "row_type",
                "sentence_id",
                "span_text",
                "occurrence",
                "concept_id",
                "canonical_name",
                "node_type",
                "aliases",
                "nested_valid",
                "boundary_notes",
            ]
        )
    return rows


def draft(dry_run: bool, max_usd: float) -> dict:
    from cumap.config import get_settings
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt

    rows = [
        tuple(r)
        for r in csv.reader((CHK / "pd_concept_pilot_sentences.csv").open(encoding="utf-8"))
    ][1:]
    prompt = load_prompt(ROOT / "prompts", "cr015_gold_draft", "v1")
    batches = []
    for sec in MAN["pilot"]:
        srows = [r for r in rows if r[1] == sec]
        for i in range(0, len(srows), BATCH):
            batches.append((sec, srows[i : i + BATCH]))
    if dry_run:
        chars = sum(
            len(
                prompt.render(
                    domain="computer networking",
                    heading_path=sec,
                    sentences="\n".join(f"{r[0]} | {r[4]}" for r in b),
                )
            )
            for sec, b in batches
        )
        t_in = chars // 4
        t_out = len(rows) * 60
        return {
            "batches": len(batches),
            "sentences": len(rows),
            "est_tokens_in": t_in,
            "est_tokens_out": t_out,
            "est_usd_strong": round(t_in / 1e6 * 2 + t_out * 3 / 1e6 * 10, 2),
            "note": "output x3 for reasoning tokens",
        }
    settings = get_settings()
    client = LLMClient(settings, run_id="cr015_pilot_gold_draft")
    client._settings.llm.max_output_tokens["cr015_gold_draft"] = 16000
    sent_text = {r[0]: r[4] for r in rows}
    bad, per_sentence = [], {}
    for sec, b in batches:
        heading = " > ".join(section_row(sec)["heading_path"] or []) or sec
        r = client.parse(
            task=prompt.task, prompt_version=prompt.version,
            messages=[{"role": "user", "content": prompt.render(domain="computer networking", heading_path=heading, sentences="\n".join(f"{x[0]} | {x[4]}" for x in b))}],
            schema=DraftBatchLLM, model_tier="strong", allow_escalation=False,
        )  # fmt: skip
        known = {x[0] for x in b}
        for s in r.output.sentences:
            if s.sentence_id in known and s.sentence_id not in per_sentence:
                per_sentence[s.sentence_id] = s.mentions
        if client.spent_usd > max_usd:
            raise SystemExit(f"stopped: ${client.spent_usd:.2f} over --max-usd {max_usd}")
    ids: dict[str, str] = {}
    types: dict[str, str] = {}
    aliases: dict[str, set[str]] = {}
    mention_rows = []
    for sid_ in [r[0] for r in rows]:
        text = sent_text[sid_]
        for m in per_sentence.get(sid_, []):
            n_occ = len(re.findall(re.escape(m.span_text), text))
            if not m.span_text.strip() or m.occurrence < 1 or m.occurrence > n_occ:
                bad.append(
                    {
                        "sentence_id": sid_,
                        "span_text": m.span_text,
                        "occurrence": m.occurrence,
                        "why": "span not found in sentence",
                    }
                )
                continue
            key = " ".join(m.concept_name.lower().split())
            cid = ids.setdefault(key, f"C{len(ids) + 1:04d}")
            types.setdefault(cid, m.node_type)
            if m.span_text.lower() != m.concept_name.lower():
                aliases.setdefault(cid, set()).add(m.span_text)
            mention_rows.append(
                (
                    "MENTION",
                    sid_,
                    m.span_text,
                    m.occurrence,
                    cid,
                    "",
                    "",
                    "",
                    "yes" if m.nested_valid else "",
                    "",
                )
            )
    names = {v: k for k, v in ids.items()}
    SUG.mkdir(parents=True, exist_ok=True)
    path = SUG / "cr015_pd_pilot_gold_draft.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "row_type",
                "sentence_id",
                "span_text",
                "occurrence",
                "concept_id",
                "canonical_name",
                "node_type",
                "aliases",
                "nested_valid",
                "boundary_notes",
                "review_decision",
            ]
        )
        for cid, name in names.items():
            w.writerow(
                [
                    "CONCEPT",
                    "",
                    "",
                    "",
                    cid,
                    name,
                    types[cid],
                    "|".join(sorted(aliases.get(cid, ()))),
                    "",
                    "",
                    "",
                ]
            )
        for row in mention_rows:
            w.writerow([*row, ""])
    summary = {
        "draft_path": str(path), "model_tier": "strong", "prompt": "cr015_gold_draft v1", "sentences": len(rows), "sentences_answered": len(per_sentence),
        "concepts": len(names), "mentions": len(mention_rows), "invalid_mentions_dropped": len(bad), "spend_usd": round(client.spent_usd, 4),
        "provenance": "MODEL_GENERATED_DIAGNOSTIC (pipeline strong tier); becomes HUMAN_REVIEWED_MODEL_DRAFT only after owner review",
    }  # fmt: skip
    (SUG / "cr015_pd_pilot_gold_draft.log.json").write_text(
        json.dumps({"summary": summary, "dropped": bad}, indent=1)
    )
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["sentences", "draft"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=3.0)
    a = ap.parse_args()
    if a.phase == "sentences":
        write_sentences(MAN["pilot"], "pd_concept_pilot")
        write_sentences(MAN["heldout_sealed"], "pd_concept_test")
        print("sentence files written for pilot and sealed held-out")
    else:
        print(json.dumps(draft(a.dry_run, a.max_usd), indent=1))
