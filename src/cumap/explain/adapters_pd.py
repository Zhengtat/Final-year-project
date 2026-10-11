"""CR-013 backfill adapter: retained run artifacts -> TraceEvents, lineage links and trace gaps. Works for the P&D production run and, with fewer artifacts,
for a retained evaluation run. Read-only: every artifact is opened for reading and hashed; nothing is written here.

Locators: `source_locator` is a JSON path inside `source_artifact` (`nodes.n_0001.mentions[3]`, or `['1.2#1']` for keys with dots); for `.jsonl` artifacts the path
starts with `line[i]`. Evidence refs are `"<artifact>::<locator>"` and resolve to the stored quote text (see lineage.resolve)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.explain.trace import NOT_RECORDED, TraceEvent, TraceStore, make_event_id

KG = REPO_ROOT / "data/processed/kg"
SAFE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def loc(*parts) -> str:
    out = ""
    for p in parts:
        if isinstance(p, int):
            out += f"[{p}]"
        elif SAFE.match(p):
            out += ("." if out else "") + p
        else:
            out += f"['{p}']"
    return out


def rel(p: Path) -> str:
    try:
        return p.relative_to(REPO_ROOT).as_posix()
    except (
        ValueError
    ):  # fixture runs live outside the repository: keep an absolute locator (still resolvable)
        return p.as_posix()


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


@dataclass
class Backfill:
    store: TraceStore = field(default_factory=TraceStore)
    links: list[dict] = field(default_factory=list)  # {child, parent, link, layer, join}
    gaps: list[dict] = field(default_factory=list)
    finals: dict[str, str] = field(
        default_factory=dict
    )  # object_id -> object_type (final KG objects)
    evidence: dict[str, list[str]] = field(default_factory=dict)  # object_id -> evidence refs
    artifacts: dict[str, str] = field(default_factory=dict)  # role -> repo path
    meta: dict = field(default_factory=dict)


class PDAdapter:
    def __init__(
        self,
        run_id: str,
        dataset_mode: str,
        *,
        org_id: str | None = None,
        sections_source: str | None = None,
        registry_version: str | None = None,
        kg_root: Path | None = None,
        calls_path: Path | None = None,
    ):
        self.run, self.mode, self.org_id, self.reg_ver = (
            run_id,
            dataset_mode,
            org_id,
            registry_version,
        )
        self.dir = (kg_root or KG) / run_id
        self.calls_path = calls_path or REPO_ROOT / "data/logs/llm_calls.jsonl"
        self.sections_path = REPO_ROOT / sections_source if sections_source else None
        self.b = Backfill()
        self.cp_path, self.v4_path = self.dir / "checkpoint.json", self.dir / "v4_concepts.json"

    # ------------------------------------------------------------------ helpers
    def ev(
        self,
        stage,
        otype,
        oid,
        action,
        outcome,
        *,
        artifact: Path,
        locator: str | None,
        doc: str = "",
        section: str | None = None,
        layer="RECORDED",
        **kw,
    ) -> TraceEvent:
        e = TraceEvent(
            event_id=make_event_id(self.run, stage, oid, action, f"{rel(artifact)}::{locator}", layer), run_id=self.run, dataset_mode=self.mode, document_id=doc or self.run,
            section_id=section, stage=stage, object_type=otype, object_id=oid, action=action, outcome=outcome, source_artifact=rel(artifact), source_locator=locator, layer=layer,
            registry_version=kw.pop("registry_version", None), **kw,
        )  # fmt: skip
        self.b.store.add(e)
        return e

    def ref(self, artifact: Path, locator: str) -> str:
        return f"{rel(artifact)}::{locator}"

    def link(
        self, child: str, parent: str, link: str, layer: str = "RECORDED", join: dict | None = None
    ) -> None:
        self.b.links.append(
            {"child": child, "parent": parent, "link": link, "layer": layer, "join": join}
        )

    def gap(
        self, scope: str, object_id: str | None, stage: str, field_: str, status: str, detail: str
    ) -> None:
        self.b.gaps.append(
            {
                "scope": scope,
                "object_id": object_id,
                "stage": stage,
                "field": field_,
                "status": status,
                "detail": detail,
            }
        )

    def evid(self, oid: str, ref: str) -> None:
        self.b.evidence.setdefault(oid, []).append(ref)

    # ------------------------------------------------------------------ build
    def build(self, replay: dict | None = None) -> Backfill:
        cp = json.loads(self.cp_path.read_text(encoding="utf-8"))
        v4 = json.loads(self.v4_path.read_text(encoding="utf-8"))
        self.b.artifacts = {"checkpoint": rel(self.cp_path), "v4_concepts": rel(self.v4_path)}
        calls = self._call_index(cp)
        sec_text = self._sections()
        self._source(v4, sec_text)
        self._generator(v4)
        self._verifier(v4)
        self._pruner(v4)
        concept_idx = self._canonicalisation(cp, v4)
        self._pairs(cp, replay)
        self._relations(cp, calls)
        snap = self._commit(cp)
        self._organisation()
        self._gaps(cp, v4, concept_idx, snap)
        self.b.meta["counts"] = {
            "events": len(self.b.store),
            "links": len(self.b.links),
            "gaps": len(self.b.gaps),
            "finals": len(self.b.finals),
        }
        return self.b

    # ------------------------------------------------------------------ call provenance (model / prompt version by input hash)
    def _call_index(self, cp: dict) -> dict:
        need = {
            h for r in cp["relation_results_v3"] for h in (r.get("prompt_hashes") or {}).values()
        }
        idx: dict[str, dict] = {}
        path = self.calls_path
        if not path.exists():
            return idx
        self.b.artifacts["llm_calls"] = rel(path)
        with path.open(encoding="utf-8") as f:
            for line in f:
                if '"input_hash": "' not in line:
                    continue
                h = line.split('"input_hash": "', 1)[1][:64]
                if h in need:
                    r = json.loads(line)
                    if h not in idx or (idx[h]["cache_hit"] and not r["cache_hit"]):
                        idx[h] = {
                            "task": r["task"],
                            "model": r["model"],
                            "prompt_version": r["prompt_version"],
                            "tier": r.get("model_tier"),
                            "cache_hit": r["cache_hit"],
                        }
        return idx

    def _sections(self) -> dict[str, str]:
        if not self.sections_path or not self.sections_path.exists():
            return {}
        self.b.artifacts["sections_source"] = rel(self.sections_path)
        return {r["section_id"]: r["text"] for r in read_jsonl(self.sections_path)}

    # ------------------------------------------------------------------ stages
    def _unit_section(self, unit: str, sec_text: dict) -> str | None:
        base = unit.split("#")[0]  # join D2: unit_to_section = strip_hash_suffix
        return base if (not sec_text or base in sec_text) else None

    def _source(self, v4: dict, sec_text: dict) -> None:
        import hashlib

        for unit in sorted(v4["sections"]):
            base = self._unit_section(unit, sec_text)
            attrs = {
                "unit": unit,
                "section_text_sha256": hashlib.sha256(sec_text[base].encode()).hexdigest()
                if base in sec_text
                else NOT_RECORDED,
            }
            self.ev(
                "source",
                "span",
                f"unit:{unit}",
                "unit_text",
                "emitted",
                artifact=self.v4_path,
                locator=loc("sections", unit),
                section=base,
                authority="STRUCTURAL",
                attrs=attrs,
            )
            if base is None:
                self.gap(
                    "object",
                    f"unit:{unit}",
                    "source",
                    "section_text",
                    "UNRESOLVED",
                    "unit id could not be mapped to a section text by stripping the # suffix",
                )
            else:
                self.link(
                    f"unit:{unit}",
                    f"section:{base}",
                    "part_of_section",
                    "JOINED",
                    {"method": "strip_hash_suffix", "key": unit},
                )

    def _generator(self, v4: dict) -> None:
        nodes = v4["nodes"]
        for nid in sorted(nodes):
            n = nodes[nid]
            sec = n["first_section"]
            reason = None
            fin = v4["sections"].get(sec, {}).get("final", {}).get("new_concepts") or []
            same = [c for c in fin if c.get("name") == n["name"]]
            if len(same) == 1:  # join (unit, exact name): one-to-one
                reason = same[0].get("independence_check")
            self.ev("generator", "concept", f"v4node:{nid}", "proposed", "accepted", artifact=self.v4_path, locator=loc("nodes", nid), section=sec.split("#")[0], authority="MODEL",
                    input_refs=[f"unit:{sec}"], attrs={"name": n["name"], "node_type": n["node_type"], "aliases": n.get("aliases", []), "first_section": sec, "recorded_reason": reason})  # fmt: skip
            self.link(f"v4node:{nid}", f"unit:{sec}", "proposed_in_unit")
            for k, m in enumerate(n["mentions"]):
                oid = f"mention:{nid}#{k}"
                evref = self.ref(self.v4_path, loc("nodes", nid, "mentions", k, "evidence"))
                self.ev("generator", "mention", oid, "mention_recorded", "accepted", artifact=self.v4_path, locator=loc("nodes", nid, "mentions", k), section=m["section_id"].split("#")[0],
                        authority="MODEL" if m.get("linked_by") == "generator" else "RULE", input_refs=[f"unit:{m['section_id']}"], output_refs=[f"v4node:{nid}"], evidence_refs=[evref],
                        attrs={"surface": m.get("surface"), "role": m.get("role"), "para": m.get("para"), "linked_by": m.get("linked_by")})  # fmt: skip
                self.link(
                    f"v4node:{nid}", oid, "supported_by_mention"
                )  # parent = mention: lineage walks concept -> node -> mentions -> evidence
                self.link(oid, f"unit:{m['section_id']}", "mention_in_unit")
                self.evid(oid, evref)

    def _verifier(self, v4: dict) -> None:
        for unit, sec in sorted(v4["sections"].items()):
            base = unit.split("#")[0]
            for it in sec["iterations"]:
                i = it["iteration"]
                for j, a in enumerate(it["autofixes"]):
                    self.ev("verifier", "mention", f"cand:{unit}:{i}:fix{j}", "autofix", "corrected", artifact=self.v4_path, locator=loc("sections", unit, "iterations", i, "autofixes", j), section=base,
                            authority="RULE", rule_id=a.get("rule"), attrs={"what": a.get("what"), "where": a.get("where")})  # fmt: skip
                for j, f in enumerate(it["flags"]):
                    self.ev("verifier", "mention", f"cand:{unit}:{i}:flag{j}", "flag_raised", "emitted", artifact=self.v4_path, locator=loc("sections", unit, "iterations", i, "flags", j), section=base,
                            authority="RULE", rule_id=f.get("rule"), reason_code=f.get("rule"), attrs={"detail": f.get("detail"), "where": f.get("where"), "idx": f.get("idx")})  # fmt: skip
                for j, h in enumerate(it["hints"]):
                    self.ev("verifier", "mention", f"cand:{unit}:{i}:hint{j}", "hint_raised", "emitted", artifact=self.v4_path, locator=loc("sections", unit, "iterations", i, "hints", j), section=base,
                            authority="RULE", rule_id=h.get("rule"), attrs={"type": h.get("type"), "text": h.get("text"), "detail": h.get("detail")})  # fmt: skip
            for j, r in enumerate(sec.get("rejected", [])):
                item = r.get("item", {})
                evq = item.get("evidence")
                self.ev("verifier", "mention", f"cand:{unit}:rej{j}", "candidate_rejected", "rejected", artifact=self.v4_path, locator=loc("sections", unit, "rejected", j), section=base,
                        authority="RULE", rule_id=(r.get("rules") or [None])[0], reason_code=",".join(r.get("rules") or []) or None,
                        evidence_refs=[self.ref(self.v4_path, loc("sections", unit, "rejected", j, "item", "evidence"))] if evq else [],
                        attrs={"kind": r.get("kind"), "surface": item.get("surface") or item.get("name"), "node_id": item.get("node_id"), "rules": r.get("rules")})  # fmt: skip
            for j, h in enumerate(sec.get("rejected_hints", [])):
                self.ev("verifier", "mention", f"cand:{unit}:rejhint{j}", "hint_rejected", "rejected", artifact=self.v4_path, locator=loc("sections", unit, "rejected_hints", j), section=base,
                        authority="MODEL", rule_id=h.get("rule"), attrs={"text": h.get("text"), "recorded_reason": h.get("reason")})  # fmt: skip

    def _pruner(self, v4: dict) -> None:
        for unit, meta in sorted(v4["section_meta"].items()):
            pruned = {
                x if isinstance(x, str) else json.dumps(x, sort_keys=True)
                for x in meta.get("pruned", [])
            }
            new_nodes = meta.get("new_nodes", [])
            names = {v4["nodes"][n]["name"]: n for n in new_nodes if n in v4["nodes"]}
            for j, p in enumerate(meta.get("p", [])):
                nid = (
                    names.get(p["name"])
                    if list(names.values()).count(names.get(p["name"])) == 1
                    else None
                )
                oid = f"v4node:{nid}" if nid else f"cand:{unit}:p{j}"
                self.ev("pruner", "concept", oid, "prune_score", "accepted" if not pruned else "not_recorded", artifact=self.v4_path, locator=loc("section_meta", unit, "p", j), section=unit.split("#")[0],
                        authority="SCORE", score=p.get("p"), threshold=None, attrs={"name": p["name"], "role": p.get("role"), "pruned_list_length": len(pruned), "joined_to_node": bool(nid)})  # fmt: skip

    def _canonicalisation(self, cp: dict, v4: dict) -> dict:
        concepts = {c["concept_id"]: c for c in cp["concepts"]}
        by_form: dict[str, set[str]] = {}
        for cid, c in concepts.items():
            for form in [c["canonical_name"], *c["aliases"]]:
                by_form.setdefault(form.lower(), set()).add(cid)
        for nid in sorted(v4["nodes"]):
            name = v4["nodes"][nid]["name"].lower()
            cands = by_form.get(name, set())
            if len(cands) == 1:
                cid = next(iter(cands))
                oid = f"concept:{cid}"
                self.link(
                    oid,
                    f"v4node:{nid}",
                    "canonical_of_v4_node",
                    "JOINED",
                    {"method": "exact_name_or_alias_unique", "key": name},
                )
                self.ev("canonicalisation", "concept", oid, f"v4_node_to_concept:{nid}", "accepted", artifact=self.v4_path, locator=loc("nodes", nid), layer="JOINED",
                        authority="STRUCTURAL", input_refs=[f"v4node:{nid}"], output_refs=[oid], join={"method": "exact_name_or_alias_unique", "key": name}, attrs={"v4_node": nid})  # fmt: skip
            else:
                self.gap(
                    "object",
                    f"v4node:{nid}",
                    "canonicalisation",
                    "concept_link",
                    "AMBIGUOUS_JOIN" if cands else "UNRESOLVED",
                    f"name {name!r} matches {len(cands)} concept(s)",
                )
        for i, m in enumerate(cp["merges"]):
            cid = m["concept_id"]
            c = concepts.get(cid, {})
            forms = {
                c.get("canonical_name", "").lower(),
                *[a.lower() for a in c.get("aliases", [])],
            }
            stage = "canonicalisation" if m["stage"].startswith("canonicalize") else "generator"
            out = (
                "merged"
                if m["auto_merged"]
                else ("merged" if m["alias"].lower() in forms else "not_recorded")
            )
            ev = (
                [self.ref(self.cp_path, loc("merges", i, "evidence_quote"))]
                if m.get("evidence_quote")
                else []
            )
            self.ev(stage, "concept", f"concept:{cid}", f"alias_link:{i}", out, artifact=self.cp_path, locator=loc("merges", i), section=m["section_id"].split("#")[0],
                    authority="RULE" if (m["auto_merged"] or m.get("rule_id")) else "MODEL", rule_id=m.get("rule_id"), score=m.get("similarity"), evidence_refs=ev,
                    attrs={"alias": m["alias"], "llm_called": m["llm_called"], "overridden": m["overridden"], "recorded_reason": m.get("reason"), "stage_recorded": m["stage"]})  # fmt: skip
        for i, m in enumerate(v4["merges"]):
            nid = m["node_id"]
            self.ev("generator", "mention", f"glink:{i}", "g_link_" + ("rejected" if m["rule_id"] == "G-link-rejected" else "accepted"), "rejected" if m["rule_id"] == "G-link-rejected" else "accepted",
                    artifact=self.v4_path, locator=loc("merges", i), section=m["section_id"].split("#")[0], authority="RULE", rule_id=m["rule_id"], input_refs=[f"v4node:{nid}"],
                    attrs={"surface": m.get("surface"), "trivial": m.get("trivial")}, evidence_refs=[self.ref(self.v4_path, loc("merges", i, "evidence"))])  # fmt: skip
        for i, t in enumerate(cp["taxonomy_candidates"]):
            self.ev("canonicalisation", "concept", f"concept:{t['concept_id']}", f"taxonomy_candidate:{i}", "not_selected", artifact=self.cp_path, locator=loc("taxonomy_candidates", i),
                    section=t["section_id"].split("#")[0], authority="MODEL", reason_code=t.get("decision"), output_refs=[f"concept:{t['matched_concept_id']}"], attrs={"recorded_reason": t.get("reason")})  # fmt: skip
        for i, t in enumerate(cp["merge_review"]):
            self.ev("canonicalisation", "concept", f"concept:{t['concept_id']}", f"merge_review:{i}", "not_recorded", artifact=self.cp_path, locator=loc("merge_review", i),
                    section=str(t["section_id"]).split("#")[0], authority="MODEL", score=t.get("similarity"), attrs={"candidate": t.get("candidate_id"), "alias": t.get("alias"), "recorded_reason": t.get("llm_reason")},
                    evidence_refs=[self.ref(self.cp_path, loc("merge_review", i, "quote"))])  # fmt: skip
        return concepts

    def _pairs(self, cp: dict, replay: dict | None) -> None:
        stats = cp["selection_stats"]
        budget, eligible = stats.get("budget"), stats.get("unique_candidate_pairs")
        for i, r in enumerate(cp["related_candidates"]):
            a, b = sorted((r["concept_id"], r["related_concept_id"]))
            self.ev("pair_generation", "pair", f"pairkey:{a}|{b}", f"related_candidate:{i}", "emitted", artifact=self.cp_path, locator=loc("related_candidates", i), section=str(r["section_id"]).split("#")[0], authority="MODEL")  # fmt: skip
        for i, a in enumerate(cp["anchors"]):
            x, y = sorted((a["concept_id"], a["anchor_id"]))
            self.ev("pair_generation", "pair", f"pairkey:{x}|{y}", f"anchor_candidate:{i}", "emitted", artifact=self.cp_path, locator=loc("anchors", i), section=str(a["section_id"]).split("#")[0], authority="RULE",
                    attrs={"anchor_type": a.get("anchor_type"), "cue": a.get("cue"), "found_via_anchor": a.get("found_via_anchor")}, evidence_refs=[self.ref(self.cp_path, loc("anchors", i, "cue"))])  # fmt: skip
        for i, p in enumerate(cp["selected_pairs"]):
            oid = f"pair:{p['pair_id']}"
            self.ev("pair_selection", "pair", oid, "selected_recorded", "selected", artifact=self.cp_path, locator=loc("selected_pairs", i), section=p["section_id"], authority="SCORE", score=float(p["cue_score"]),
                    eligible_count=eligible, budget=budget, input_refs=[f"concept:{p['concept_x_id']}", f"concept:{p['concept_y_id']}"], evidence_refs=[self.ref(self.cp_path, loc("selected_pairs", i, "sentence"))],
                    attrs={"cooccurrence_count": p["cooccurrence_count"], "rank": NOT_RECORDED, "phase": NOT_RECORDED, "sentence": p["sentence"], "origin": "anchor pair (retained pair id prefix AP-): entered selection from the anchors, not ranked in the candidate pool" if p["pair_id"].startswith("AP-") else "candidate-pool pair (retained pair id prefix RP-)"})  # fmt: skip
            self.link(oid, f"concept:{p['concept_x_id']}", "endpoint_x")
            self.link(oid, f"concept:{p['concept_y_id']}", "endpoint_y")
            self.evid(oid, self.ref(self.cp_path, loc("selected_pairs", i, "sentence")))
        anchor_by_key: dict[str, list[int]] = {}
        for i, a in enumerate(cp["anchors"]):
            anchor_by_key.setdefault(
                "|".join(sorted((a["concept_id"], a["anchor_id"]))), []
            ).append(i)
        for i, p in enumerate(cp["selected_pairs"]):
            if not p["pair_id"].startswith("AP-"):
                continue
            key = "|".join(sorted((p["concept_x_id"], p["concept_y_id"])))
            hits = anchor_by_key.get(key, [])
            if len(hits) == 1:
                a = cp["anchors"][hits[0]]
                self.ev("pair_generation", "pair", f"pair:{p['pair_id']}", "anchor_pair_join", "emitted", artifact=self.cp_path, locator=loc("anchors", hits[0]), section=str(a["section_id"]).split("#")[0],
                        layer="JOINED", authority="RULE", join={"method": "anchor_pair_unique_key", "key": key}, attrs={"anchor_type": a.get("anchor_type"), "cue": a.get("cue")},
                        evidence_refs=[self.ref(self.cp_path, loc("anchors", hits[0], "cue"))])  # fmt: skip
            else:
                self.gap(
                    "object",
                    f"pair:{p['pair_id']}",
                    "pair_generation",
                    "anchor_record",
                    "AMBIGUOUS_JOIN" if hits else "UNRESOLVED",
                    f"{len(hits)} anchor records for pair key {key}",
                )
        for i, p in enumerate(cp["sample_pairs"]):
            self.ev("pair_selection", "pair", f"pair:{p['pair_id']}", "unselected_sample_recorded", "not_selected", artifact=self.cp_path, locator=loc("sample_pairs", i), section=p["section_id"], authority="SCORE",
                    score=float(p["cue_score"]), eligible_count=eligible, budget=budget, attrs={"sampled_for_measurement": True, "cooccurrence_count": p["cooccurrence_count"]})  # fmt: skip
            self.link(f"pair:{p['pair_id']}", f"concept:{p['concept_x_id']}", "endpoint_x")
            self.link(f"pair:{p['pair_id']}", f"concept:{p['concept_y_id']}", "endpoint_y")
        self.b.meta["replay"] = {"enabled": replay is not None, "valid": bool(replay and replay["valid"]), "mismatches": (replay or {}).get("mismatches", []), "eligible_count": (replay or {}).get("eligible_count"),
                                 "code_hashes": (replay or {}).get("code_hashes")}  # fmt: skip
        if not replay or not replay["valid"]:
            self.gap(
                "run",
                None,
                "pair_selection",
                "rank_and_pool",
                "NOT_RECORDED",
                "per-pair rank and the eligible pool are not retained; the replay layer is "
                + ("invalid: " + "; ".join(replay["mismatches"]) if replay else "not enabled"),
            )
            return
        for row in replay["pool"]:
            oid = f"pair:{row['pair_id']}"
            common = dict(  # noqa: C408
                artifact=self.cp_path,
                locator="selection_stats",
                section=row["section_id"],
                layer="REPLAYED",
                authority="SCORE",
                score=float(row["cue_score"]),
                eligible_count=replay["eligible_count"],
                budget=replay["budget"],
            )
            self.ev("pair_generation", "pair", oid, "pool_pair_replayed", "emitted", **common, attrs={"pair_key": row["pair_key"], "cooccurrence_count": row["cooccurrence_count"], "section_pool": row["section_pool"], "section_rank": row["section_rank"]})  # fmt: skip
            self.ev("pair_selection", "pair", oid, "rank_replayed", "selected" if row["selected"] else "not_selected", **common, rank=row["global_rank"], input_refs=[f"concept:{row['concept_x_id']}", f"concept:{row['concept_y_id']}"],
                    attrs={"in_unselected_sample": row["in_unselected_sample"], "section_rank": row["section_rank"], "section_pool": row["section_pool"], "pair_key": row["pair_key"], "rank_key": row["rank_key"]})  # fmt: skip
            self.link(
                oid,
                f"concept:{row['concept_x_id']}",
                "endpoint_x",
                "RECORDED" if row["selected"] or row["in_unselected_sample"] else "REPLAYED",
            )
            self.link(
                oid,
                f"concept:{row['concept_y_id']}",
                "endpoint_y",
                "RECORDED" if row["selected"] or row["in_unselected_sample"] else "REPLAYED",
            )

    def _relations(self, cp: dict, calls: dict) -> None:
        seen: dict[str, int] = {}
        for i, r in enumerate(cp["relation_results_v3"]):
            pid = r["pair"]["pair_id"]
            n = seen.get(pid, 0)
            seen[pid] = n + 1
            oid, pobj = f"relrow:{pid}:{n}", f"pair:{pid}"
            hashes = r.get("prompt_hashes") or {}
            cl = {k: {"hash": h, **calls.get(h, {})} for k, h in hashes.items()}
            main = calls.get(hashes.get("choice")) or calls.get(hashes.get("family")) or {}
            outcome = {
                "edge": "emitted",
                "rejected": "emitted",
                "no_relation": "no_relation",
                "other": "no_relation",
                "same_concept": "no_relation",
            }.get(r["outcome"], "not_recorded")
            evq = (
                [self.ref(self.cp_path, loc("relation_results_v3", i, "evidence_quote"))]
                if r.get("evidence_quote")
                else []
            )
            attrs = {
                k: r.get(k)
                for k in (
                    "outcome",
                    "family",
                    "relation",
                    "direction",
                    "statement",
                    "evidence_quote",
                    "qualifiers",
                    "family_reason",
                    "comparison_dimension",
                    "other_description",
                    "grounding",
                    "type_errors",
                    "group",
                )
            }
            attrs.update(
                {
                    "calls": cl,
                    "choice_set": "see the prompt text for the choice hash in data/logs/llm_prompts.jsonl",
                    "confidence": NOT_RECORDED,
                }
            )
            self.ev("relation_classification", "pair", oid, "classify_pair", outcome, artifact=self.cp_path, locator=loc("relation_results_v3", i), section=r["pair"]["section_id"], authority="MODEL",
                    reason_code=r.get("reason"), model_id=main.get("model"), prompt_version=main.get("prompt_version"), registry_version=self.reg_ver, input_refs=[pobj],
                    evidence_refs=[self.ref(self.cp_path, loc("relation_results_v3", i, "pair", "sentence")), *evq], attrs=attrs)  # fmt: skip
            if (
                pid.startswith("MP-") and n == 0
            ):  # misconception-stage verification pair (CR-008): not produced by pair selection
                self.ev("pair_generation", "pair", pobj, "misconception_verification_pair", "emitted", artifact=self.cp_path, locator=loc("relation_results_v3", i, "pair"), section=r["pair"]["section_id"],
                        authority="MODEL", input_refs=[f"concept:{r['pair']['concept_x_id']}", f"concept:{r['pair']['concept_y_id']}"], attrs={"origin": "misconception-structuring verification pair (retained pair id prefix MP-), created outside pair selection"})  # fmt: skip
                self.link(pobj, f"concept:{r['pair']['concept_x_id']}", "endpoint_x")
                self.link(pobj, f"concept:{r['pair']['concept_y_id']}", "endpoint_y")
            self.link(oid, pobj, "classification_of_pair")
            self.evid(
                oid, self.ref(self.cp_path, loc("relation_results_v3", i, "pair", "sentence"))
            )
            if r["outcome"] in ("edge", "rejected"):
                self.ev("validation", "pair", oid, "validate_relation", "accepted" if r["outcome"] == "edge" else "rejected", artifact=self.cp_path, locator=loc("relation_results_v3", i), section=r["pair"]["section_id"],
                        authority="RULE", reason_code=r.get("reason"), input_refs=[oid], evidence_refs=evq, attrs={"grounding": r.get("grounding"), "type_errors": r.get("type_errors"), "relation": r.get("relation")})  # fmt: skip

    def _commit(self, cp: dict) -> dict:
        snap = {"edges": {}, "nodes": {}}
        base = self.dir / "snapshots"
        if not base.exists():
            self.gap(
                "run",
                None,
                "graph_commit",
                "snapshots",
                "NOT_RECORDED",
                "this run has no per-chapter snapshots: the final graph is taken from the checkpoint concepts and its edge relation rows (no commit record exists)",
            )
            self.b.meta["finals_source"] = "checkpoint (no snapshots)"
            counts: dict[str, int] = {}
            for c in cp["concepts"]:
                self.b.finals[f"concept:{c['concept_id']}"] = "concept"
            for i, r in enumerate(cp["relation_results_v3"]):
                pid = r["pair"]["pair_id"]
                if (
                    r["outcome"] != "edge"
                    or r.get("group") != "selected"
                    or r.get("gated_dropped")
                    or r.get("consolidated_into")
                ):
                    continue
                n = counts.get(pid, 0)
                counts[pid] = n + 1
                eobj = f"edge:{pid}"
                self.b.finals[eobj] = "edge"
                self.link(
                    eobj,
                    f"relrow:{pid}:{n}",
                    "final_edge_is_checkpoint_row",
                    "JOINED",
                    {"method": "checkpoint_edge_row", "key": pid},
                )
                for end, key in (("source", "concept_x_id"), ("target", "concept_y_id")):
                    self.link(eobj, f"concept:{r['pair'][key]}", f"endpoint_{end}")
                self.evid(
                    eobj, self.ref(self.cp_path, loc("relation_results_v3", i, "evidence_quote"))
                )
                self.evid(
                    eobj, self.ref(self.cp_path, loc("relation_results_v3", i, "pair", "sentence"))
                )
            return snap
        for ch in sorted(int(p.name[2:]) for p in base.glob("ch*") if p.is_dir()):
            for fname, kind in (("nodes.jsonl", "nodes"), ("edges.jsonl", "edges")):
                p = base / f"ch{ch}" / fname
                self.b.artifacts[f"snapshot_ch{ch}_{kind}"] = rel(p)
                for i, row in enumerate(read_jsonl(p)):
                    if kind == "nodes":
                        cid = row["concept_id"]
                        self.ev("graph_commit", "concept", f"concept:{cid}", "commit_node", "accepted", artifact=p, locator=loc("line", i), authority="STRUCTURAL", attrs={"first_introduced_chapter": row.get("first_introduced_chapter"), "mention_section_count": row.get("mention_section_count")})  # fmt: skip
                        self.b.finals[f"concept:{cid}"] = "concept"
                        snap["nodes"][cid] = (p, i)
                    else:
                        eid = row["edge_id"]
                        self.ev("graph_commit", "edge", f"edge:{eid}", "commit_edge", "accepted", artifact=p, locator=loc("line", i), section=row.get("section_id"), authority="STRUCTURAL", input_refs=[f"relrow:{eid}"],
                                attrs={k: row.get(k) for k in ("source_concept_id", "relation", "target_concept_id", "family", "source_chapter", "target_chapter")})  # fmt: skip
                        self.b.finals[f"edge:{eid}"] = "edge"
                        snap["edges"][eid] = (p, i, row)
        return snap

    def _organisation(self) -> None:
        if not self.org_id:
            self.gap(
                "run",
                None,
                "organisation",
                "organisation",
                "NOT_RECORDED",
                "this run has no organisation output",
            )
            return
        base = self.dir / "organisation" / self.org_id
        if not base.exists():
            self.gap(
                "run",
                None,
                "organisation",
                "organisation",
                "NOT_RECORDED",
                f"organisation {self.org_id} not found",
            )
            return
        for ch in sorted(int(p.name[2:]) for p in base.glob("ch*") if p.is_dir()):
            p = base / f"ch{ch}" / "events.jsonl"
            self.b.artifacts[f"organisation_ch{ch}_events"] = rel(p)
            for i, e in enumerate(read_jsonl(p)):
                for sid in dict.fromkeys(e["subject_ids"]):
                    self.ev("organisation", "organisation_record", f"{'community' if e['type'].startswith('community') else 'concept'}:{sid}", f"org_event:{ch}:{i}:{e['type']}", "emitted", artifact=p, locator=loc("line", i), authority="STRUCTURAL", reason_code=e["type"],
                            attrs={"chapter": ch, "from_state": e.get("from_state"), "to_state": e.get("to_state"), "delta_importance": e.get("delta_importance"), "because_edge_ids": e.get("because_edge_ids"), "because_section_ids": e.get("because_section_ids")})  # fmt: skip

    # ------------------------------------------------------------------ links + gaps that need all stages
    def _gaps(self, cp: dict, v4: dict, concepts: dict, snap: dict) -> None:
        rows: dict[str, list[int]] = {}
        for i, r in enumerate(cp["relation_results_v3"]):
            rows.setdefault(r["pair"]["pair_id"], []).append(i)
        for eid, (p, i, row) in sorted(snap["edges"].items()):
            cands = [
                (k, n)
                for n, k in enumerate(rows.get(eid, []))
                if cp["relation_results_v3"][k]["outcome"] == "edge"
                and cp["relation_results_v3"][k].get("group") == "selected"
            ]
            edge_obj = f"edge:{eid}"
            for end, key in (("source", "source_concept_id"), ("target", "target_concept_id")):
                self.link(edge_obj, f"concept:{row[key]}", f"endpoint_{end}")
            if len(cands) == 1:
                k, n = cands[0]
                self.link(
                    edge_obj,
                    f"relrow:{eid}:{n}",
                    "committed_from_relation_row",
                    "JOINED",
                    {"method": "equal_pair_id_unique", "key": eid},
                )
                self.ev("graph_commit", "edge", edge_obj, "edge_to_relation_row", "accepted", artifact=p, locator=loc("line", i), layer="JOINED", authority="STRUCTURAL", join={"method": "equal_pair_id_unique", "key": eid}, input_refs=[f"relrow:{eid}:{n}"])  # fmt: skip
                self.evid(
                    edge_obj,
                    self.ref(self.cp_path, loc("relation_results_v3", k, "evidence_quote")),
                )
                self.evid(
                    edge_obj,
                    self.ref(self.cp_path, loc("relation_results_v3", k, "pair", "sentence")),
                )
            else:
                self.gap(
                    "object",
                    edge_obj,
                    "graph_commit",
                    "relation_row",
                    "AMBIGUOUS_JOIN" if cands else "UNRESOLVED",
                    f"{len(cands)} candidate relation rows with outcome edge for pair id {eid}",
                )
        edge_rows = [
            (r["pair"]["pair_id"], i)
            for i, r in enumerate(cp["relation_results_v3"])
            if r["outcome"] == "edge" and r.get("group") == "selected"
        ]
        for pid, i in edge_rows:
            if snap["edges"] and pid not in snap["edges"]:
                self.gap(
                    "object",
                    f"relrow:{pid}",
                    "graph_commit",
                    "edge_commit",
                    "INCONSISTENT",
                    f"relation row {i} has outcome 'edge' but no snapshot edge with id {pid}",
                )
        for pid, idxs in rows.items():
            sel = [i for i in idxs if cp["relation_results_v3"][i].get("group") == "selected"]
            if len(sel) > 1:
                self.gap(
                    "object",
                    f"pair:{pid}",
                    "relation_classification",
                    "relation_row",
                    "INCONSISTENT",
                    f"{len(sel)} selected relation rows for one pair id: {sel}",
                )
        for cid in concepts:
            if f"concept:{cid}" not in self.b.finals and snap["nodes"]:
                self.gap(
                    "object",
                    f"concept:{cid}",
                    "graph_commit",
                    "node_commit",
                    "INCONSISTENT",
                    "concept in the checkpoint but not in any snapshot",
                )

        index = {c["concept_id"]: i for i, c in enumerate(cp["concepts"])}
        for cid, i in index.items():
            for k, m in enumerate(cp["concepts"][i]["mentions"]):
                if m.get("quote"):
                    self.evid(
                        f"concept:{cid}",
                        self.ref(self.cp_path, loc("concepts", i, "mentions", k, "quote")),
                    )
        # run-level gaps found by the STOP-1 audit
        n_alias = sum(1 for c in cp["concepts"] if c["alias_provenance"])
        if n_alias == 0:
            self.gap(
                "run",
                None,
                "canonicalisation",
                "alias_provenance",
                "NOT_RECORDED",
                "alias_provenance and merged_from are empty on every concept (legacy run); the v4-node link is an exact name join",
            )
        self.gap(
            "run",
            None,
            "canonicalisation",
            "blocked_merges",
            "NOT_RECORDED",
            "no retained record of blocked merges (lexicon DIFFERENT veto) in this run",
        )
        self.gap(
            "run",
            None,
            "generator",
            "input_hash_link",
            "NOT_RECORDED",
            "generator calls are not linked to sections/iterations by input hash in the retained artifacts",
        )
        self.gap(
            "run",
            None,
            "relation_classification",
            "confidence",
            "NOT_RECORDED",
            "no confidence or score is stored with relation decisions; rejected alternatives are only in the prompt text",
        )
        self.gap(
            "run",
            None,
            "pruner",
            "threshold",
            "NOT_RECORDED",
            "the pruner threshold is not stored in the artifact (run recipe: pruner off, tau 0)",
        )
