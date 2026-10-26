"""CR-059: draft a domain profile from the domain's own documents, without gold ($ cents, one strong-tier call through `llm/client.py`).

    uv run python -m cumap.cr059.draft --dry-run                # the rendered prompt size and cost estimate, no call
    uv run python -m cumap.cr059.draft --limit 2                # 2 papers only
    uv run python -m cumap.cr059.draft                          # the default sample (3 SciNLP train papers of the first set)

Writes `data/interim/suggestions/domain_profile_<name>_draft.yaml` (status: draft) and a log of every term whose quote failed the check
(rule 3: dropped with a reason, never kept). The owner reviews and edits the draft, then approves it by writing it to
`configs/domain_profiles/<name>_v1.yaml` with `status: approved`; code never approves. The sample is read for the documents' text only
(no gold), from training papers (rule 9)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from cumap.config import REPO_ROOT, get_settings
from cumap.cr059.domain_profile import CATEGORIES, Category
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt

OUT = REPO_ROOT / "data/interim/suggestions"
PURPOSE_SCINLP = (
    "An expert knowledge graph of each research paper: the specific scientific content the paper studies, proposes, uses, "
    "evaluates or compares, and how these relate, so that a reader's understanding of the paper can later be compared with it."
)
CHUNK_WORDS = 700
MAX_OUTPUT_TOKENS = (
    6000  # ten categories with quoted examples and two word lists; the default 1000 truncates
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuotedTermLLM(_Strict):
    term: str
    quote: str


class CategoryDraftLLM(_Strict):
    category: Category  # type: ignore[valid-type]
    include: bool
    scope: Literal["named_only", "any"]
    examples: list[QuotedTermLLM]
    reason: str


class DomainProfileDraftLLM(_Strict):
    document_kind: str
    domain: str
    domain_description: str
    specificity: Literal["named_instances", "field_terms"]
    specificity_reason: str
    categories: list[CategoryDraftLLM]
    always_concepts: list[QuotedTermLLM]
    not_alone: list[QuotedTermLLM]
    acronym_convention: Literal[
        "long_form_with_acronym_alias", "keep_parenthesised_acronym_in_span"
    ]
    keep_variant_modifier: bool


def _norm(s: str) -> str:
    return " ".join((s or "").split())


def quote_ok(t: QuotedTermLLM, sample: str) -> str | None:
    """None when the quote is an exact (whitespace-normalised) substring of the sample and contains the term; else the reason."""
    q = _norm(t.quote)
    if not q or q not in sample:
        return "quote_not_in_sample"
    if _norm(t.term).lower() not in q.lower():
        return "term_not_in_quote"
    return None


def excerpts(text: str, k: int = 2, words: int = CHUNK_WORDS) -> list[str]:
    """The opening excerpt and one from the middle of a document (deterministic)."""
    w = text.split()
    if len(w) <= words:
        return [" ".join(w)]
    starts = [0, max(0, len(w) // 2 - words // 2)][:k]
    return [" ".join(w[s : s + words]) for s in starts]


def render_sample(docs: list[tuple[str, str]]) -> tuple[str, int]:
    parts, n = [], 0
    for i, (_key, text) in enumerate(docs, 1):
        for j, ex in enumerate(excerpts(text), 1):
            parts.append(f"[document {i}, excerpt {j}]\n{ex}")
            n += 1
    return "\n\n".join(parts), n


def category_list() -> str:
    return "\n".join(f"   - {k}: {v}" for k, v in CATEGORIES.items())


def to_profile(
    out: DomainProfileDraftLLM, sample: str, name: str, provenance: dict
) -> tuple[dict, list[dict]]:
    """Draft profile dict (status draft) and the log of dropped terms. A category the model left out is recorded as include: false."""
    dropped: list[dict] = []

    def keep(items: list[QuotedTermLLM], where: str, cap: int) -> list[dict]:
        seen, kept = set(), []
        for t in items:
            why = quote_ok(t, sample)
            if why:
                dropped.append({"where": where, "term": t.term, "reason": why})
                continue
            k = _norm(t.term).lower()
            if k in seen:
                continue
            seen.add(k)
            kept.append({"term": _norm(t.term), "quote": _norm(t.quote)})
        return kept[:cap]

    cats = {}
    for c in out.categories:
        cats[c.category] = {"include": c.include, "scope": c.scope,
                            "examples": keep(c.examples, f"category:{c.category}", 4), "reason": c.reason}  # fmt: skip
    for k in CATEGORIES:
        if k not in cats:
            cats[k] = {
                "include": False,
                "scope": "named_only",
                "examples": [],
                "reason": "not decided by the drafter",
            }
            dropped.append(
                {"where": f"category:{k}", "term": "", "reason": "category_missing_set_to_false"}
            )
    prof = {
        "name": name,
        "version": 1,
        "status": "draft",
        "document_kind": _norm(out.document_kind).lower(),
        "domain": _norm(out.domain),
        "domain_description": _norm(out.domain_description),
        "specificity": out.specificity,
        "specificity_reason": _norm(out.specificity_reason),
        "categories": cats,
        "always_concepts": keep(out.always_concepts, "always_concepts", 20),
        "not_alone": keep(out.not_alone, "not_alone", 20),
        "acronym_convention": out.acronym_convention,
        "keep_variant_modifier": out.keep_variant_modifier,
        "provenance": provenance,
    }
    return prof, dropped


def default_sample(n: int) -> list[tuple[str, str]]:
    """The first `n` train papers of the CR-043 first set (fixed hash order), text only; the other 37 train papers stay untouched."""
    from cumap.cr012 import scinlp_run as SR
    from cumap.cr012.adapters import SciNLPAdapter
    from cumap.cr043.papers import first_set

    keys = [d for s, d in first_set() if s == "train"][:n]
    docs = {
        d.doc_key: d
        for d in SciNLPAdapter().load_documents("train", paragraph_every=SR.PARAGRAPH_EVERY)
    }
    return [(k, re.sub(r"\s+", " ", docs[k].text)) for k in keys]


def draft(docs: list[tuple[str, str]], purpose: str, name: str, client: LLMClient | None, *, dry_run: bool,
          fixture: str = "default") -> dict:  # fmt: skip
    prompt = load_prompt(REPO_ROOT / "prompts", "domain_profile", "v1")
    sample, n_chunks = render_sample(docs)
    rendered = prompt.render(category_list=category_list(), purpose=purpose, n_docs=str(len(docs)),
                             n_chunks=str(n_chunks), sample=sample)  # fmt: skip
    if dry_run:
        tiers = get_settings().llm.tiers
        t = tiers["strong"]
        tok = len(rendered) / 3.5
        usd = tok / 1e6 * (t.usd_per_1m_input_tokens or 0) + MAX_OUTPUT_TOKENS / 1e6 * (
            t.usd_per_1m_output_tokens or 0
        )
        return {"dry_run": True, "papers": [k for k, _ in docs], "excerpts": n_chunks, "input_tokens_est": round(tok),
                "usd_worst_est": round(usd, 4), "model_tier": "strong"}  # fmt: skip
    assert client is not None
    res = client.parse(task="domain_profile", prompt_version=prompt.version, messages=[{"role": "user", "content": rendered}],
                       schema=DomainProfileDraftLLM, model_tier="strong", fixture_name=fixture)  # fmt: skip
    prov = {"drafter_prompt": f"domain_profile/{prompt.version}", "model": res.model, "input_hash": res.input_hash,
            "sample_papers": [k for k, _ in docs], "excerpt_words": CHUNK_WORDS, "purpose": purpose,
            "drafted_on": datetime.now(UTC).date().isoformat(), "gold_used": False, "reviewed_by": None}  # fmt: skip
    prof, dropped = to_profile(res.output, " ".join(_norm(t) for _, t in docs), name, prov)
    return {"profile": prof, "dropped": dropped}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="scinlp")
    ap.add_argument("--papers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="use at most this many papers")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    n = min(a.papers, a.limit) if a.limit else a.papers
    docs = default_sample(n)
    if a.dry_run:
        print(json.dumps(draft(docs, PURPOSE_SCINLP, a.name, None, dry_run=True), indent=1))
        return
    run_id = f"cr059_profile_draft_{a.name}"
    settings = get_settings()
    # default.yaml is hash-pinned (CR-011 handoff), so this task's output limit is set here
    settings.llm.max_output_tokens.setdefault("domain_profile", MAX_OUTPUT_TOKENS)
    out = draft(docs, PURPOSE_SCINLP, a.name, LLMClient(settings, run_id=run_id), dry_run=False)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"domain_profile_{a.name}_draft.yaml"
    p.write_text(
        yaml.safe_dump(out["profile"], sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (OUT / f"domain_profile_{a.name}_draft_dropped.json").write_text(
        json.dumps(out["dropped"], indent=1), encoding="utf-8"
    )
    print(
        json.dumps(
            {"draft": str(p.relative_to(REPO_ROOT)), "dropped_terms": len(out["dropped"])}, indent=1
        )
    )


if __name__ == "__main__":
    main()
