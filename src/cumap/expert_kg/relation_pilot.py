"""CR-007 STOP 3 pilot: re-classify the CR-005 OTHER pairs (114 `relation_other` pairs of the P&D ch2-3
run) with registry v1.1 and relation prompts v3, and show where each one lands. Strong tier through
LLMClient, budget-capped ($2 pre-approved), results and exact prompt hashes saved under
data/processed/pilot/<run_id>/."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.pipeline import _restore_concept_registry, load_checkpoint
from cumap.expert_kg.relations import CandidatePair, concept_vocab
from cumap.expert_kg.relations_v3 import V3Result, classify_pair_v3
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

# measured per real call in CR-005 (strong tier), scaled up for the longer v3 prompts
EST_USD_PER_PAIR = {"family": 0.0025, "choice": 0.0045, "qualifiers": 0.0035}


def load_other_pairs(run_dir: Path, sections_jsonl: Path, reason: str = "relation_other") -> list[dict]:
    cp = load_checkpoint(run_dir)
    texts = {}
    with sections_jsonl.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            texts[r["section_id"]] = r["text"]
    out = []
    for i, p in enumerate(cp.pair_registry):
        if p.get("edge") or p.get("reason") != reason or not p.get("evidence_sentences"):
            continue
        sentence = p["evidence_sentences"][0]
        sec = next((sid for sid, t in texts.items() if sentence in t), "")
        out.append({"pilot_id": f"PILOT-{len(out) + 1}", "section_id": sec, "concept_x_id": p["concept_x_id"],
                    "concept_y_id": p["concept_y_id"], "sentence": sentence})
    return out


def estimate_usd(n_pairs: int) -> float:
    return n_pairs * (EST_USD_PER_PAIR["family"] + EST_USD_PER_PAIR["choice"] + 0.5 * EST_USD_PER_PAIR["qualifiers"])


def run_pilot(client: LLMClient, run_dir: Path, pairs: list[dict], registry: RelationRegistry,
              prompts_dir: Path, *, prompt_version: str = "v3", progress=None) -> list[V3Result]:
    cp = load_checkpoint(run_dir)
    concepts = {c.concept_id: c for c in _restore_concept_registry(cp, lambda t: None).all()}
    matcher = MentionMatcher(concept_vocab(list(concepts.values())))
    fam, rel, qual = (load_prompt(prompts_dir, t, prompt_version)
                      for t in ("relation_family", "relation_choice", "relation_qualifiers"))
    out: list[V3Result] = []
    for i, p in enumerate(pairs):
        pair = CandidatePair(p["pilot_id"], p["section_id"], p["concept_x_id"], p["concept_y_id"], p["sentence"])
        out.append(classify_pair_v3(client, fam, rel, qual, registry, pair, concepts[p["concept_x_id"]],
                                    concepts[p["concept_y_id"]], matcher))
        if progress and (i + 1) % 10 == 0:
            progress(f"{i + 1}/{len(pairs)} pairs, spend ${client.spent_usd:.3f}")
    return out


def summarise(results: list[V3Result], names: dict[str, str]) -> dict:
    by_outcome = Counter(r.outcome for r in results)
    rejected = Counter(r.reason for r in results if r.outcome == "rejected")
    accepted = Counter((r.family, r.relation) for r in results if r.outcome == "edge")
    landing = Counter(r.relation or r.reason for r in results if r.outcome in ("edge", "rejected") and r.relation)
    domain = Counter(r.relation for r in results if r.reason == "domain_range")
    ground_quote = sum(1 for r in results if r.reason == "endpoint_not_grounded")
    rescued = sum(1 for r in results if r.reason == "endpoint_not_grounded"
                  and r.grounding.get("sentence_x") and r.grounding.get("sentence_y"))
    labels = Counter((r.other_suggested_label or "").lower() for r in results if r.outcome == "other" and r.other_suggested_label)
    return {"n": len(results), "outcome": dict(by_outcome), "rejected_reasons": dict(rejected),
            "accepted_by_relation": {f"{f}/{r}": c for (f, r), c in accepted.most_common()},
            "attempted_by_relation": dict(landing.most_common()), "domain_range_by_relation": dict(domain),
            "endpoint_not_grounded": ground_quote, "endpoint_grounded_in_sentence_but_not_quote": rescued,
            "other_labels": dict(labels.most_common(15)), "names": names}


def group_examples(results: list[V3Result], names: dict[str, str], per: int = 3) -> dict[str, list[dict]]:
    ex: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        key = r.relation if r.outcome == "edge" else (f"[{r.outcome}] {r.reason}")
        if len(ex[key]) < per:
            ex[key].append({"x": names[r.pair.concept_x_id], "y": names[r.pair.concept_y_id], "sentence": r.pair.sentence,
                            "relation": r.relation, "direction": r.direction, "statement": r.statement,
                            "quote": r.evidence_quote, "action_type": r.qualifiers.get("action_type"),
                            "polarity": r.qualifiers.get("polarity"), "other": r.other_description,
                            "label": r.other_suggested_label, "reason": r.reason, "family": r.family})
    return ex
