"""CR-019 Stage B: multi-sentence evidence for relation classification (pre-registered in DECISIONS.md 2026-10-15, owner cap $25).

Arms: SINGLE = the unchanged production relation stage (family v3 / choice v4 / qualifiers v4, first co-occurring sentence);
MULTI = family v4 / choice v5 / qualifiers v5 on a PASSAGE of up to K = 3 sentences of the same section in which both concepts occur
(the pair's original sentence first, then the others in text order). MULTI runs on a copy of the SINGLE run (same concepts, same selected
pairs) under a new run id; only the relation stage is re-run. Data: SciNLP dev (6 papers) and P&D development sections 1.5 / 2.6.

    uv run python -m cumap.cr019.stage_b baseline --doc P02-1004.grobid [--dry-run]     # SciNLP dev E0 (SINGLE) run
    uv run python -m cumap.cr019.stage_b multi --base <run_id> [--limit 20] [--dry-run]  # MULTI relation stage on a copy
    uv run python -m cumap.cr019.stage_b spend                                           # Stage B spend so far (cap $25)
    uv run python -m cumap.cr019.stage_b score                                           # reports/cr019/stage_b.{json,md}
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT, get_settings
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import unit_run as UR
from cumap.expert_kg.mentions import MentionMatcher, build_vocab
from cumap.expert_kg.relations import split_sentences

CAP_USD = 25.0
K = 3
MULTI_VERSIONS = ("v4", "v5", "v5")
SC_DEV = [
    "2021.acl-long.295",
    "2024.acl-long.144-1-9.grobid",
    "P05-1008.grobid",
    "P16-1007.grobid",
    "P02-1004.grobid",
    "P03-1014.grobid",
]
PD_DEV = ["1.5", "2.6"]
KG = REPO_ROOT / "data/processed/kg"
OUT = REPO_ROOT / "reports/cr019"


def slug(doc: str) -> str:
    return doc.replace(".", "_").replace("-", "_")


def sc_base(doc: str) -> str:
    return f"cr012_scinlp_cr019dev_{slug(doc)}_E0"


def pd_base(sid: str) -> str:
    return f"cr012_pilot_{sid.replace('.', '_')}_E0"


def multi_id(base: str) -> str:
    return f"cr019b_multi_{base}"


def all_runs() -> list[str]:
    bases = [sc_base(d) for d in SC_DEV] + [pd_base(s) for s in PD_DEV]
    return [sc_base(d) for d in SC_DEV] + [multi_id(b) for b in bases]


# ---------------------------------------------------------------- environment per unit (same recipe as the CR-012 runs)
def use_unit(base: str) -> Path:
    """Set the environment the base run was produced under; -> the unit's sections.jsonl."""
    for d in SC_DEV:
        if base == sc_base(d):
            doc = next(
                x
                for x in SR.SciNLPAdapter().load_documents(
                    "dev", paragraph_every=SR.PARAGRAPH_EVERY
                )
                if x.doc_key == d
            )
            info = SR.prepare("dev", doc)
            prof = yaml.safe_load(SR.PROFILE.read_text())
            os.environ.update(
                {
                    "CUMAP_DEMO_SLICE": info["slice_config"],
                    "CUMAP_BENCHMARK_PROFILE": str(SR.PROFILE),
                    "CUMAP_RELATION_REGISTRY": prof["relation_registry"],
                }
            )
            get_settings.cache_clear()
            return Path(info["slice_config"]).parent / "sections.jsonl"
    for s in PD_DEV:
        if base == pd_base(s):
            info = UR.prepare(s)
            os.environ["CUMAP_DEMO_SLICE"] = info["slice_config"]
            os.environ.pop("CUMAP_BENCHMARK_PROFILE", None)
            os.environ.pop("CUMAP_RELATION_REGISTRY", None)
            get_settings.cache_clear()
            return Path(info["slice_config"]).parent / "sections.jsonl"
    raise ValueError(f"not a Stage B base run: {base}")


# ---------------------------------------------------------------- the MULTI evidence passage
def passage(
    sentences: list[str], cids_by_sentence: list[set[str]], pair: dict, k: int = K
) -> tuple[str, int]:
    """Up to k sentences containing both concepts: the pair's original sentence first, then the others in text order."""
    x, y = pair["concept_x_id"], pair["concept_y_id"]
    both = [i for i, c in enumerate(cids_by_sentence) if x in c and y in c]
    first = [i for i in both if sentences[i] == pair["sentence"]]
    order = first[:1] + [i for i in both if i not in first[:1]]
    chosen = order[:k]
    if not first:  # the original evidence is not a single split sentence (a sentence span): keep it as the first line
        lines = [pair["sentence"]] + [sentences[i] for i in chosen[: k - 1]]
    else:
        lines = [sentences[i] for i in chosen]
    return "\n".join(lines), len(lines)


def evidence_fn_for(cp_concepts: list[dict], section_texts: dict[str, str]):
    matcher = MentionMatcher(build_vocab(cp_concepts))
    cache: dict[str, tuple[list[str], list[set[str]]]] = {}

    def fn(p: dict) -> dict:
        sid = p["section_id"]
        if sid not in cache:
            sents = split_sentences(section_texts[sid])
            cache[sid] = (sents, [{m.concept_id for m in matcher.find(s)} for s in sents])
        text, _n = passage(*cache[sid], p)
        return {**p, "sentence": text}

    return fn


# ---------------------------------------------------------------- spend (hard cap)
def spend() -> dict:
    from cumap.llm.cost import spend_from_log

    st = get_settings()
    per = {r: round(spend_from_log(st, r), 4) for r in all_runs()}
    return {"per_run": {k: v for k, v in per.items() if v}, "total_usd": round(sum(per.values()), 4), "cap_usd": CAP_USD}  # fmt: skip


def _remaining() -> float:
    return CAP_USD - spend()["total_usd"]


def run_baseline(doc: str, *, dry_run: bool, max_usd: float) -> dict:
    rem = _remaining()
    if not dry_run and rem < max_usd:
        raise SystemExit(
            f"Stage B cap: ${rem:.2f} left of ${CAP_USD}, run asks for up to ${max_usd}"
        )
    return SR.run_doc("dev", doc, "cr019dev", dry_run=dry_run, max_usd=max_usd)


def run_multi(base: str, *, limit: int | None, dry_run: bool, max_usd: float) -> dict:
    from cumap.concepts_v4 import experiments as X
    from cumap.expert_kg import slice_rerun as sr
    from cumap.expert_kg.pipeline import load_checkpoint, save_checkpoint
    from cumap.llm.client import LLMClient
    from cumap.schemas.relations import RelationRegistry

    src = use_unit(base)
    rid = multi_id(base)
    if not (KG / base / "checkpoint.json").exists():
        raise SystemExit(f"base run {base} not found")
    if not (KG / rid).exists():
        (KG / rid).mkdir(parents=True)
        for f in ("checkpoint.json", "v4_concepts.json"):
            if (KG / base / f).exists():
                shutil.copy2(KG / base / f, KG / rid / f)
        cp = load_checkpoint(KG / rid)
        cp.relation_results_v3 = []
        cp.stage = "relations"
        save_checkpoint(cp, KG / rid)
    cp = load_checkpoint(KG / rid)
    pre = sr.preflight_relations(cp)
    pre_multi = {
        **pre,
        "est_usd_upper_multi": round(pre["est_usd_upper"] * 2.2, 4),
    }  # longer passages: ~2.2x input tokens (measured on the limit-20 step)
    if dry_run:
        return {"dry_run": True, "run_id": rid, **pre_multi}
    rem = _remaining()
    if rem < max_usd:
        raise SystemExit(
            f"Stage B cap: ${rem:.2f} left of ${CAP_USD}, run asks for up to ${max_usd}"
        )
    settings = get_settings()
    settings.llm.stage_budgets_usd["relations"] = max_usd
    client = LLMClient(settings, run_id=rid)
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    texts = {
        json.loads(line)["section_id"]: json.loads(line)["text"]
        for line in src.read_text().splitlines()
        if line.strip()
    }
    raw = json.loads((KG / rid / "checkpoint.json").read_text())
    cp = sr.relations_stage(
        client, cp, KG / rid, registry, REPO_ROOT / "prompts", X.Embedder(settings.embeddings.model),
        progress=print, prompt_versions=MULTI_VERSIONS, evidence_fn=evidence_fn_for(raw["concepts"], texts), limit=limit,
    )  # fmt: skip
    return {"run_id": rid, "results": len(cp.relation_results_v3), "pairs": pre["pairs"], "spend_usd": round(client.spent_usd, 4)}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["baseline", "multi", "spend", "score"])
    ap.add_argument("--doc")
    ap.add_argument("--base")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=3.0)
    a = ap.parse_args()
    if a.cmd == "baseline":
        out = run_baseline(a.doc, dry_run=a.dry_run, max_usd=a.max_usd)
    elif a.cmd == "multi":
        out = run_multi(a.base, limit=a.limit, dry_run=a.dry_run, max_usd=a.max_usd)
    elif a.cmd == "spend":
        out = spend()
    else:
        from cumap.cr019.stage_b_score import main as score

        out = score()
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
