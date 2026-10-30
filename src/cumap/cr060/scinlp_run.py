"""CR-060 / CR-061: the frozen CR-012 SciNLP runner with profile v11 (`configs/scinlp_profile_v11.yaml`: profile v5 + the CR-060
head-variant identity rule, variant A-name, at assembly; v10 = A-all is superseded). Same mechanism as `cumap.cr056.scinlp_run`; the frozen runner is not edited. After a paper's run the checkpoint
is rewritten with the span-identity step applied; the pre-step checkpoint is kept as `checkpoint_pre_span_identity.json` (a resumed run
starts from it, so the relation stage never sees merged nodes) and the record as `span_identity.json`. Train / dev only (rule 9).

    uv run python -m cumap.cr060.scinlp_run run --split dev --doc <doc> ..."""

from __future__ import annotations

import json
import shutil

import yaml

from cumap.config import REPO_ROOT
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr056.scinlp_run import all_pairs
from cumap.cr060 import span_identity as SI

PROFILE_V10 = REPO_ROOT / "configs/scinlp_profile_v10.yaml"  # A-all, superseded (CR-061)
PROFILE_V11 = REPO_ROOT / "configs/scinlp_profile_v11.yaml"  # A-name, adopted (CR-061)
PRE = "checkpoint_pre_span_identity.json"


def apply_to_run(run_dir, doc, variant: str) -> dict:
    """Apply the span-identity step to a finished run directory (idempotent: always from the pre-step checkpoint)."""
    cp_path, pre = run_dir / "checkpoint.json", run_dir / PRE
    if not pre.exists():
        shutil.copyfile(cp_path, pre)
    cp0 = json.loads(pre.read_text(encoding="utf-8"))
    sym = frozenset(SciNLPAdapter().symmetric_relations())
    cp, rec = SI.apply(cp0, doc.text, SI.load_variant(variant), symmetric=sym)
    cp_path.write_text(json.dumps(cp, indent=1, ensure_ascii=False), encoding="utf-8")
    (run_dir / "span_identity.json").write_text(
        json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return cp["selection_stats"]["span_identity"]


def with_span_identity(variant: str) -> None:
    """Wrap `SR.run_doc`: restore the pre-step checkpoint before a (resumed) run, apply the step after it."""
    inner = SR.run_doc

    def run_doc(split: str, doc_key: str, tag: str, *, dry_run: bool, max_usd: float) -> dict:
        run_id = f"cr012_scinlp_{tag}_{doc_key.replace('.', '_').replace('-', '_')}_E0"
        run_dir = REPO_ROOT / "data/processed/kg" / run_id
        if (run_dir / PRE).exists():
            shutil.copyfile(run_dir / PRE, run_dir / "checkpoint.json")
        out = inner(split, doc_key, tag, dry_run=dry_run, max_usd=max_usd)
        if not dry_run:
            doc = next(d for d in SciNLPAdapter().load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)
                       if d.doc_key == doc_key)  # fmt: skip
            out["span_identity"] = apply_to_run(run_dir, doc, variant)
        return out

    SR.run_doc = run_doc


def use_profile(path=PROFILE_V11) -> None:
    SR.PROFILE = path
    prof = yaml.safe_load(path.read_text())
    if prof.get("pair_budget") == "all":
        SR.pair_budget = all_pairs
    if prof.get("span_identity"):
        with_span_identity(prof["span_identity"])


if __name__ == "__main__":
    use_profile()
    SR.main()
