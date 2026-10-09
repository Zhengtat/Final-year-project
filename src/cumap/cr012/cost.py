"""CR-012 cost preflight (D4: soft warning $40, hard cap $50, mandatory scope only). Unit rates are measured on the STOP 3 pilot E0 run (see
the constants below). 'upper' = no cache sharing between oracle runs; 'lower' = byte-identical calls reused where the
oracle did not alter the call (E3 and E4 classify the same gold pairs, so E4 is then free). Stability repeats never share a cache.
Replaced by measured numbers after the STOP 3 rehearsal; STOP 4 may not start if the refreshed total exceeds the cap."""

from __future__ import annotations

import json

from cumap.config import REPO_ROOT

# measured on the STOP 3 pilot E0 run of section 1.5 (3.64k words, 52 pairs): concepts $0.0033 and canonicalisation $0.0165 per 1k words,
# relations $0.0062 per selected pair (many selected pairs end at the family step). Forced GOLD pairs are mostly true edges and need all three
# steps, so they keep the earlier $0.0083.
PAIR_USD = 0.0062
GOLD_PAIR_USD = 0.0083
CONCEPT, CANON = 0.0033, 0.0165
REL_BUDGET = 14.2 * PAIR_USD  # per 1k words
GOLD_PAIRS_PER_1K = {
    "pd": 18.0,  # 118 unique pilot gold edges / 6.56k words, measured on the owner-reviewed pilot
    "scinlp": 17.0,  # 295 test relations / 17.4k words
}
WORDS_K = {
    "pd_pilot": 6.564,
    "pd_heldout": 30.053,
    "scinlp_test": 17.4,  # 20,468 tokens x 0.85
    "scinlp_dev_rehearsal": 9.5,  # about two dev documents
    "stability_run": 3.255 + 4.091 + (6504 + 6798) * 0.85 / 1000,
}


def per_1k(kind: str, sharing: bool) -> dict[str, float]:
    g = GOLD_PAIRS_PER_1K[kind] * GOLD_PAIR_USD
    e = {
        "E0": CONCEPT + CANON + REL_BUDGET,
        "E1": CANON + REL_BUDGET,
        "E2": REL_BUDGET,
        "E3": g,
        "E4": 0.0 if sharing else g,
    }
    if sharing:
        e["E1"] *= 0.8
        e["E2"] *= 0.85
    return e


def build() -> dict:
    out = {}
    for sharing in (False, True):
        tag = "lower_cache_sharing" if sharing else "upper_no_sharing"
        pd_h = sum(per_1k("pd", sharing).values()) * WORDS_K["pd_heldout"]
        sc_h = (
            sum(v for k, v in per_1k("scinlp", sharing).items() if k != "E2")
            * WORDS_K["scinlp_test"]
        )  # E2 not supported on SciNLP
        pilot = (
            sum(per_1k("pd", sharing)[k] for k in ("E0", "E1", "E3")) * WORDS_K["pd_pilot"]
        ) + (
            sum(per_1k("scinlp", sharing)[k] for k in ("E0", "E1", "E3"))
            * WORDS_K["scinlp_dev_rehearsal"]
        )
        stab = (
            3 * per_1k("pd", False)["E0"] * WORDS_K["stability_run"]
        )  # independent repeats never share a cache
        out[tag] = {
            "pilot": round(pilot, 2),
            "heldout_pd": round(pd_h, 2),
            "heldout_scinlp": round(sc_h, 2),
            "stability": round(stab, 2),
            "total": round(pilot + pd_h + sc_h + stab, 2),
        }
    out["limits"] = {"soft_warning": 40, "hard_cap": 50}
    out["words_k"] = WORDS_K
    out["status"] = (
        "UPPER BELOW CAP"
        if out["upper_no_sharing"]["total"] <= 50
        else "UPPER ABOVE CAP: return to Research before STOP 4"
    )
    return out


if __name__ == "__main__":
    r = build()
    (REPO_ROOT / "reports/cr012/cost_preflight.json").write_text(
        json.dumps(r, indent=1), encoding="utf-8"
    )
    print(json.dumps(r, indent=1))
