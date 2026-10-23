"""CR-014 frozen V3 core: one-token evidence ranker, boundary repair + verifier flow (run_v2), and the candidate-span helpers.
Deliberately free of any gold, scorer or dev-data import so that held-out prediction code cannot reach gold (CR-014 STOP 4 isolation).
Moved verbatim from stage_b.py before the V3 freeze; behaviour is unchanged (checked by a cache-hit replay of a pilot section)."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import yaml

from cumap.cr014.llm_stage import Usage, run_boundary, run_verifier  # noqa: F401
from cumap.cr014.proposal import definitional_hits, norm_surface
from cumap.cr014.union import Cand, SectionUnion, surface_regex

ROOT = Path(".")
CFG = yaml.safe_load((ROOT / "configs/cr014_concept_extraction.yaml").read_text())
SB = CFG["stage_b"]
DOMAIN = "information retrieval"  # default; callers pass `domain` explicitly
ACCEPT = {"ACCEPT_NEW", "LINK_EXISTING"}


# ---------------------------------------------------------------- one-token ranker (prioritisation score, fixed a priori)
def onetoken_features(u: SectionUnion, heading: str) -> dict[str, dict[str, float]]:
    defs = definitional_hits(u.text)
    head_words = set(re.findall(r"\w+", heading.lower()))
    multi_last: dict[str, int] = {}
    multi_mod: dict[str, int] = {}
    for c in u.cands.values():
        if c.token_length >= 2 and c.count >= 2:
            toks = c.surface.split()
            multi_last[toks[-1]] = multi_last.get(toks[-1], 0) + 1
            for t in toks[:-1]:
                multi_mod[t] = multi_mod.get(t, 0) + 1
    feats_by: dict[str, dict[str, float]] = {}
    for c in u.cands.values():
        if c.token_length != 1:
            continue
        a, b, _ = c.occurrences[0]
        raw = u.text[a:b]
        v = {
            "definitional": float(c.surface in defs or "definitional" in c.sources),
            "heading": float(c.surface in head_words or "heading" in c.sources),
            "emphasis": float("emphasis" in c.sources),
            "acronym": float(("acronym" in c.sources) or (raw.isupper() and len(raw) >= 2)),
            "recurrence": min(c.count / 10, 1.0),
            "llm_agreement": float("llm_iter0" in c.sources),
            "head_of_multiword": float(
                multi_last.get(c.surface, 0) + multi_mod.get(c.surface, 0) > 0
            ),
            "technical_pos": float("noun_span" in c.sources),
        }
        feats_by[c.cid] = v
    return feats_by


def onetoken_scores(u: SectionUnion, heading: str) -> dict[str, float]:
    feats = CFG["one_token"]["features"]
    w = CFG["one_token"]["weights"]
    return {
        cid: sum(w[f] * v[f] for f in feats) / sum(w[f] for f in feats)
        for cid, v in onetoken_features(u, heading).items()
    }


def evidence_text(c: Cand, v: dict[str, float]) -> str:
    """Term evidence for a one-word candidate (shown to the V3 verifier; supports but never decides)."""
    bits = [f"occurs {c.count}x"]
    for k, label in (
        ("definitional", "in a definition sentence"),
        ("heading", "in the section heading"),
        ("emphasis", "emphasised in the text"),
        ("acronym", "acronym/upper-case"),
        ("head_of_multiword", "part of longer recurring terms"),
    ):
        if v.get(k):
            bits.append(label)
    return "evidence: " + ", ".join(bits)


# ---------------------------------------------------------------- arms


@dataclasses.dataclass
class SectionOutcome:
    accepted: dict[str, dict] = dataclasses.field(
        default_factory=dict
    )  # surface -> record (verdict, family, source cids)
    verdicts: dict[str, dict] = dataclasses.field(
        default_factory=dict
    )  # cid-or-span id -> verdict + surface
    boundary: dict[str, list[dict]] = dataclasses.field(
        default_factory=dict
    )  # family id -> decisions
    gated: list[str] = dataclasses.field(default_factory=list)
    invalid_spans: list[dict] = dataclasses.field(default_factory=list)
    unaddressed: list[str] = dataclasses.field(default_factory=list)
    n_verified: int = 0
    n_boundary_families: int = 0


def new_span_cand(u: SectionUnion, surface: str, n: int) -> Cand | None:
    key = norm_surface(surface)
    if key in u.cands:
        return u.cands[key]
    occ = [(m.start(), m.end(), 0) for m in surface_regex(key).finditer(u.text)]
    if not occ:
        return None
    import bisect

    occ = [(a, b, max(bisect.bisect_right(u.sent_starts, a) - 1, 0)) for a, b, _ in occ]
    c = Cand(f"{u.section_id}#s{n:05d}", key, u.section_id, len(key.split()), {"boundary_repair"})
    c.count, c.occurrences = len(occ), occ[:40]
    return c


def run_v2(
    client,
    prompt_v,
    prompt_b,
    u,
    heading,
    matches,
    usage,
    only: set[str] | None = None,
    evidence: bool = False,
    domain: str | None = None,
) -> SectionOutcome:
    domain = domain or DOMAIN
    out = SectionOutcome()
    by_id = {c.cid: c for c in u.cands.values()}
    active = {cid for cid in by_id if only is None or cid in only}
    out.gated = sorted(set(by_id) - active)
    need, pass_through = [], []
    for f in u.families:
        mem = [m for m in f.members if m in active]
        if not mem:
            continue
        g = dataclasses.replace(f, members=mem)
        (need if len(mem) >= 2 else pass_through).append(g)
    out.n_boundary_families = len(need)
    dec = run_boundary(client, prompt_b, u, heading, need, by_id, SB, domain, usage)
    out.boundary = dec
    spans: dict[str, tuple[Cand, list[str]]] = {}
    n_new = 0
    for f in pass_through:
        c = by_id[f.members[0]]
        spans.setdefault(c.surface, (c, []))[1].append(c.cid)
    for f in need:
        ds = dec.get(f.fid)
        if ds is None:
            out.unaddressed += f.members  # the model gave no answer for this family
            continue
        addressed: set[str] = set()
        sent_text = " ".join(
            re.sub(r"\s+", " ", u.text[u.sents[si][0] : u.sents[si][1]].lower())
            for _, _, si in f.occurrences[:3]
        )
        for d in ds:
            addressed |= set(d["source_candidate_ids"])
            if d["decision"] == "REJECT" or not d["surface"]:
                continue
            key = norm_surface(d["surface"])
            if len(key.split()) > CFG["stage_b"]["max_boundary_words"] or key not in sent_text:
                out.invalid_spans.append(
                    {"family": f.fid, "surface": d["surface"], "why": "not_in_source_or_too_long"}
                )
                continue
            c = new_span_cand(u, key, n_new)
            if c is None:
                out.invalid_spans.append(
                    {"family": f.fid, "surface": d["surface"], "why": "not_in_section"}
                )
                continue
            n_new += c.cid.count("#s")
            spans.setdefault(c.surface, (c, []))[1].extend(d["source_candidate_ids"] or [c.cid])
        out.unaddressed += [m for m in f.members if m not in addressed]
    cs = sorted((c for c, _ in spans.values()), key=lambda c: c.cid)
    extra = None
    if (
        evidence
    ):  # V3: one-word candidates carry their evidence and are verified in priority (score) order
        fe = onetoken_features(u, heading)
        sc = onetoken_scores(u, heading)
        cs = sorted(cs, key=lambda c: (c.token_length != 1, -sc.get(c.cid, 0.0), c.cid))
        extra = {
            c.cid: (evidence_text(c, fe[c.cid]) if c.cid in fe else "evidence: n/a (multi-word)")
            for c in cs
        }
    out.n_verified = len(cs)
    vs = run_verifier(client, prompt_v, u, heading, cs, SB, matches, domain, usage, extra=extra)
    for c in cs:
        v = vs.get(c.cid)
        out.verdicts[c.cid] = {"surface": c.surface, **(v or {"verdict": "NO_ANSWER"})}
        if v and v["verdict"] in ACCEPT:
            out.accepted[c.surface] = {
                "verdict": v["verdict"],
                "source_cids": sorted(set(spans[c.surface][1])),
                "node_id": v["node_id"],
            }
    return out
