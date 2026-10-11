"""CR-013 trace build: retained artifacts -> derived trace under `data/processed/explainability/<run>/<explain_id>/`. Never writes into the source run.

uv run python -m cumap.explain.build --run slice3_c2
uv run python -m cumap.explain.build --run cr012_scinlp_heldout_P17_1058_grobid_E0 --no-replay
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT
from cumap.explain.adapters_pd import KG, PDAdapter
from cumap.explain.coverage import coverage
from cumap.explain.lineage import Lineage
from cumap.explain.render import RENDERER_VERSION, render_event
from cumap.explain.trace import SCHEMA_VERSION

CFG = yaml.safe_load((REPO_ROOT / "configs/cr013_explainability.yaml").read_text())


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_files(run: str, sections_source: str | None) -> list[Path]:
    base = KG / run
    files = [
        base / "checkpoint.json",
        base / "v4_concepts.json",
        REPO_ROOT / "data/logs/llm_calls.jsonl",
    ]
    files += sorted(p for p in base.rglob("*.jsonl")) + sorted(base.rglob("manifest.json"))
    if sections_source:
        files.append(REPO_ROOT / sections_source)
    return [p for p in files if p.exists()]


def code_hash() -> str:
    h = hashlib.sha256()
    for p in sorted((REPO_ROOT / "src/cumap/explain").glob("*.py")) + [
        REPO_ROOT / "configs/cr013_explainability.yaml"
    ]:
        h.update(p.name.encode() + sha(p).encode())
    return h.hexdigest()[:16]


def build(run: str, *, replay_enabled: bool = True, out_root: Path | None = None) -> dict:
    is_pd = run == CFG["production"]["run_id"]
    cfgp = CFG["production"] if is_pd else CFG["evaluation_example"]
    sections_source = CFG["production"]["sections_source"] if is_pd else None
    files = source_files(run, sections_source)
    before = {p.relative_to(REPO_ROOT).as_posix(): sha(p) for p in files}

    replay = None
    if is_pd and replay_enabled and CFG["production"]["replay"]["enabled"]:
        from cumap.concepts_v4 import experiments as X
        from cumap.config import get_settings
        from cumap.expert_kg import slice_rerun as sr
        from cumap.explain.replay import replay_pair_pool
        from cumap.schemas.relations import RelationRegistry

        st = get_settings()
        sections = sr.load_sections(
            REPO_ROOT / sections_source, list(CFG["production"]["chapters"])
        )
        reg = RelationRegistry.from_yaml(REPO_ROOT / st.relation_registry)
        embed = X.Embedder(st.embeddings.model)
        replay = replay_pair_pool(
            KG / run,
            sections,
            reg,
            embed,
            budget=CFG["production"]["replay"]["budget"],
            use_anchors=CFG["production"]["replay"]["use_anchors"],
        )
        replay2 = replay_pair_pool(
            KG / run,
            sections,
            reg,
            embed,
            budget=CFG["production"]["replay"]["budget"],
            use_anchors=CFG["production"]["replay"]["use_anchors"],
        )
        replay["deterministic"] = json.dumps(replay["pool"], sort_keys=True) == json.dumps(
            replay2["pool"], sort_keys=True
        )

    def one_pass():
        from cumap.config import get_settings

        reg_ver = (
            yaml.safe_load((REPO_ROOT / get_settings().relation_registry).read_text()).get(
                "version"
            )
            if is_pd
            else None
        )
        ad = PDAdapter(
            run,
            cfgp["dataset_mode"],
            org_id=CFG["production"]["organisation_id"] if is_pd else None,
            sections_source=sections_source,
            registry_version=str(reg_ver) if reg_ver else None,
        )
        return ad, ad.build(replay)

    _ad, bf = one_pass()
    _, bf2 = one_pass()
    sec_text = {}
    if sections_source:
        sec_text = {
            json.loads(x)["section_id"]: json.loads(x)["text"]
            for x in (REPO_ROOT / sections_source).read_text(encoding="utf-8").splitlines()
            if x.strip()
        }
    lin = Lineage(bf.links, bf.finals, bf.evidence)
    cov = coverage(bf.store, lin, bf.finals, sec_text, bf.gaps)
    explain_id = hashlib.sha1(
        (
            json.dumps(before, sort_keys=True)
            + code_hash()
            + RENDERER_VERSION
            + SCHEMA_VERSION
            + str(bool(replay and replay["valid"]))
        ).encode()
    ).hexdigest()[:12]
    out = (out_root or REPO_ROOT / CFG["output_root"]) / run / explain_id
    out.mkdir(parents=True, exist_ok=True)
    h1 = bf.store.to_jsonl(out / "trace_events.jsonl")
    h2 = bf2.store.to_jsonl(out / ".events_second_pass.tmp")
    (out / ".events_second_pass.tmp").unlink()
    lineage_records = lin.records(bf.store)
    (out / "object_lineage.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in lineage_records)
        + "\n",
        encoding="utf-8",
    )
    (out / "trace_gaps.jsonl").write_text(
        "\n".join(
            json.dumps(g, sort_keys=True, ensure_ascii=False)
            for g in sorted(bf.gaps, key=lambda g: json.dumps(g, sort_keys=True))
        )
        + "\n",
        encoding="utf-8",
    )
    idx_lines = []
    for eid in sorted(bf.store.events):
        r = render_event(bf.store.events[eid])
        idx_lines.append(
            json.dumps(
                {
                    "event_id": eid,
                    "object_id": r["object_id"],
                    "stage": r["stage"],
                    "authority": r["authority"],
                    "layer": r["layer"],
                    "text": r["text"],
                    "support": r["support"],
                    "unrecorded": r["unrecorded"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    (out / "explanation_index.jsonl").write_text("\n".join(idx_lines) + "\n", encoding="utf-8")
    if replay:
        (out / "replay_pool.jsonl").write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in replay["pool"]) + "\n",
            encoding="utf-8",
        )
    after = {p.relative_to(REPO_ROOT).as_posix(): sha(p) for p in files}
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT, check=False
    ).stdout.strip()
    manifest = {
        "explain_id": explain_id, "source_run_id": run, "dataset_mode": cfgp["dataset_mode"], "trace_schema_version": SCHEMA_VERSION, "renderer_version": RENDERER_VERSION, "code_version_git_head": git,
        "explain_code_hash": code_hash(), "base_commit": CFG["base_commit"], "source_artifacts": before, "source_hashes_after_build": after, "source_hashes_unchanged": before == after,
        "stage_artifacts": bf.artifacts, "counts": bf.meta["counts"], "replay": {k: v for k, v in bf.meta["replay"].items()} | ({"deterministic": replay.get("deterministic")} if replay else {}),
        "coverage": cov, "replay_determinism_trace_hash_equal": h1 == h2, "trace_events_sha256": h1, "known_trace_gaps": [g for g in bf.gaps if g["scope"] == "run"],
        "outputs": sorted(p.name for p in out.iterdir()),
    }  # fmt: skip
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    return {"dir": str(out.relative_to(REPO_ROOT)), "manifest": manifest}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=CFG["production"]["run_id"])
    ap.add_argument("--no-replay", action="store_true")
    a = ap.parse_args()
    r = build(a.run, replay_enabled=not a.no_replay)
    m = r["manifest"]
    print(
        json.dumps(
            {
                "dir": r["dir"],
                "counts": m["counts"],
                "replay": m["replay"],
                "unchanged": m["source_hashes_unchanged"],
                "replay_trace_hash_equal": m["replay_determinism_trace_hash_equal"],
                "coverage": m["coverage"],
            },
            indent=1,
            default=str,
        )[:6000]
    )


if __name__ == "__main__":
    main()
