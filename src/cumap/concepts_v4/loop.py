"""CR-009 §3.3-3.4 and §4.2-4.3: the generator call and the PiVe-style corrective loop.

One section at a time. Iteration 0 is the generator's output; the verifier (code) checks it. If it is not
Correct, a CORRECTIONS block (one instruction per error type found + the accumulated GIVEN ITEMS) is added to
the ORIGINAL prompt and the generator is run again from scratch ("regenerate, don't patch"; in G2 only Pass B is
re-run). The generator MAY reject a hint with a reason (a deviation from PiVe, which adds triples outright).
Hints accumulate; a clean item that vanishes without a rejection is carried forward. The same model is used in
every iteration (no escalation). Every iteration's output is stored so analysis can be replayed."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field

from cumap.concepts_v4.bank import card_line, render_examples
from cumap.concepts_v4.cards import Card
from cumap.concepts_v4.schema import ConceptGeneratorV4LLM
from cumap.concepts_v4.verifier import (
    Hint,
    VerifyCtx,
    VerifyResult,
    drop_flagged,
    flagged_items,
    verify,
)
from cumap.llm.client import BudgetExceededError, LLMClient
from cumap.llm.prompts import PromptTemplate

PASS_A_NOTE = (
    "THIS IS THE OPEN PASS: do steps 1 and 6 only. No known nodes are shown, so every term is a NEW independent "
    'concept (extraction_origin independent, anchors empty, independence_check "No existing nodes were given.").\n\n'
)


@dataclass
class LoopConfig:
    form: str = "G2"  # G1 | G2
    model_tier: str = "bulk"
    max_iterations: int = 3
    per_section_call_budget: int = 5
    drop_max: int = 3
    carry_forward: bool = True
    use_verifier: bool = True
    # C-SAC arm: SAC-KG's own checks only, one regeneration, no coverage rules
    rules: str = "all"  # all | sac (Q1 + F1-F3 only)
    stop_after_regen: int | None = None  # SAC: regenerate at most once
    hints_forced: bool = (
        False  # C-PiVe: given items are added outright (the generator may not reject them)
    )
    hint_rules: tuple[str, ...] = ("M1", "M2", "M3", "M4", "M5")
    bank_corrective: bool = True
    instructions: dict[str, str] = field(default_factory=dict)
    prefix: str = (
        "Extract the concepts again, and also review the given items. Include each one the text supports, "
        "with role and exact evidence, or reject it with a reason."
    )


@dataclass
class SectionResult:
    section_id: str
    iterations: list[dict] = field(
        default_factory=list
    )  # {iteration, output, flags, hints, autofixes, warnings}
    final: dict = field(default_factory=dict)
    rejected: list[dict] = field(default_factory=list)  # dropped by a rule, with the rule id
    rejected_hints: list[dict] = field(default_factory=list)
    unconfirmed_mentions: list[str] = field(default_factory=list)
    unresolved_hints: list[dict] = field(default_factory=list)
    calls: int = 0
    stop_reason: str = ""
    restored: int = 0
    iteration0: dict = field(default_factory=dict)
    terms_pass_a: list[str] = field(default_factory=list)
    flags_by_rule: dict = field(default_factory=dict)
    hints_added: int = 0
    hints_rejected: int = 0
    error: str | None = None


def render_cards(cards: list[Card]) -> str:
    return "\n".join(card_line(c.to_bank_card()) for c in cards) or "(none: no known nodes yet)"


def render_look_alikes(lexicon, cards: list[Card], text: str, chapter: int | None) -> str:
    if lexicon is None:
        return ""
    names = {c.node.name.lower() for c in cards} | {
        f.lower() for c in cards for f in c.node.forms()
    }
    lines = []
    for e in lexicon.approved("different"):
        if len(e.forms) == 2 and (
            any(f.lower() in names for f in e.forms)
            or any(re.search(rf"\b{re.escape(f)}\b", text, re.IGNORECASE) for f in e.forms)
        ):
            lines.append(f"{e.forms[0]} / {e.forms[1]}: {e.why or e.kind}")
    return ("LOOK-ALIKES (never the same node):\n" + "\n".join(lines) + "\n\n") if lines else ""


def render_paragraphs(paras: dict[str, str]) -> str:
    return "\n".join(f"{k}: {' '.join(v.split())}" for k, v in paras.items())


def render_corrections(flags, hints: list[Hint], cfg: LoopConfig) -> str:
    by_rule: dict[str, list[str]] = {}
    for f in flags:
        by_rule.setdefault(f.rule, []).append(f.detail)
    lines = []
    for rule, items in by_rule.items():
        tmpl = cfg.instructions.get(rule)
        if tmpl:
            lines.append(f"- {tmpl.replace('{items}', '; '.join(items[:6]))}")
    for rule in sorted({h.rule for h in hints}):
        tmpl = cfg.instructions.get(rule)
        if tmpl:
            lines.append(
                f"- {tmpl.replace('{items}', '; '.join(h.text for h in hints if h.rule == rule)[:400])}"
            )
    block = "CORRECTIONS (your previous answer was checked by rules):\n" + "\n".join(lines) + "\n"
    if hints:
        block += (
            "GIVEN ITEMS (hint_id | type | text | detail):\n"
            + "\n".join(f"{h.hint_id} | {h.type} | {h.text} | {h.detail}" for h in hints)
            + "\n"
        )
        block += "Answer every given item in hint_responses (added or rejected with a reason).\n"
    return block + cfg.prefix + "\n\n"


class SectionRunner:
    def __init__(
        self,
        client: LLMClient,
        prompt: PromptTemplate,
        bank: dict,
        cfg: LoopConfig,
        *,
        domain: str,
        fixture: str = "default",
    ):
        self.client, self.prompt, self.bank, self.cfg, self.domain, self.fixture = (
            client,
            prompt,
            bank,
            cfg,
            domain,
            fixture,
        )

    # ---------------------------------------------------------------- one generator call
    def _call(
        self,
        sec: dict,
        paras: dict[str, str],
        cards: list[Card],
        lexicon,
        *,
        pass_a: bool,
        terms: list[str],
        corrections: str,
        corrective: bool,
    ) -> dict:
        mode = "pass_a" if pass_a else "full"
        rendered = self.prompt.render(
            domain=self.domain,
            examples=render_examples(self.bank, mode, corrective=corrective and not pass_a),
            heading_path=str(sec.get("heading") or sec["section_id"]),
            look_alikes=""
            if pass_a
            else render_look_alikes(lexicon, cards, sec["text"], sec.get("chapter_num")),
            existing_nodes="(not shown in this pass)" if pass_a else render_cards(cards),
            independent_terms=(
                "TERMS FOUND BY AN INDEPENDENT READER (check each; the list may be incomplete or wrong):\n"
                + "\n".join(f"- {t}" for t in terms)
                + "\n\n"
            )
            if terms and not pass_a
            else "",
            corrections=corrections,
            section_paragraphs=render_paragraphs(paras),
            pass_note=PASS_A_NOTE if pass_a else "",
        )
        res = self.client.parse(
            task="concept_generator",
            prompt_version=self.prompt.version,
            messages=[{"role": "user", "content": rendered}],
            schema=ConceptGeneratorV4LLM,
            model_tier=self.cfg.model_tier,
            fixture_name=self.fixture,
            allow_escalation=False,
        )
        return res.output.model_dump()

    # ---------------------------------------------------------------- the loop
    def run(
        self, sec: dict, paras: dict[str, str], cards: list[Card], lexicon, vctx_base: VerifyCtx
    ) -> SectionResult:
        cfg = self.cfg
        res = SectionResult(sec["section_id"])
        terms: list[str] = []
        try:
            if cfg.form == "G2":
                a = self._call(
                    sec, paras, [], None, pass_a=True, terms=[], corrections="", corrective=False
                )
                res.calls += 1
                terms = [c["name"] for c in a["new_concepts"]]
                res.terms_pass_a = terms
            out = self._call(
                sec,
                paras,
                cards,
                lexicon,
                pass_a=False,
                terms=terms,
                corrections="",
                corrective=False,
            )
            res.calls += 1
        except BudgetExceededError:
            raise
        except Exception as e:  # noqa: BLE001  # schema failure after the client's own handling: no items
            res.error = f"{type(e).__name__}: {str(e)[:200]}"
            res.final = {
                "existing_mentions": [],
                "not_mentions": [],
                "new_concepts": [],
                "hint_responses": [],
            }
            res.stop_reason = "error"
            return res
        if not cfg.use_verifier:
            res.final, res.stop_reason = out, "no_verifier"
            res.iterations.append(
                {
                    "iteration": 0,
                    "output": out,
                    "flags": [],
                    "hints": [],
                    "autofixes": [],
                    "warnings": [],
                }
            )
            res.iteration0 = out
            return res

        hints: dict[tuple[str, str], Hint] = {}  # accumulated, in order of first sight
        rejected_keys: set[tuple[str, str]] = set()
        clean: dict[
            tuple[str, str], tuple[str, dict]
        ] = {}  # key -> (kind, item) that passed every rule earlier
        q1_rounds = 0
        regen = 0
        prev_sig = None
        last_vr: VerifyResult | None = None
        for it in range(cfg.max_iterations + 1):
            vctx = copy.copy(vctx_base)
            vctx.rejected_keys = set(rejected_keys)
            vr = verify(out, vctx)
            vr = self._filter(vr, cfg, q1_rounds)
            last_vr = vr
            rec = {
                "iteration": it,
                "output": out,
                "verified": vr.out,
                "flags": [f.__dict__ for f in vr.flags],
                "hints": [
                    {"rule": h.rule, "type": h.type, "text": h.text, "detail": h.detail}
                    for h in vr.hints
                ],
                "autofixes": vr.autofixes,
                "warnings": vr.warnings,
            }
            res.iterations.append(rec)
            if it == 0:
                res.iteration0 = vr.out
            for f in vr.flags:
                res.flags_by_rule[f.rule] = res.flags_by_rule.get(f.rule, 0) + 1
            flagged = flagged_items(vr.flags)
            for kind, key, nm in _item_keys(vr.out):
                if (
                    ("mention" if kind == "existing_mentions" else "new"),
                    _idx(vr.out, kind, nm),
                ) not in flagged:
                    clean[(kind, nm)] = (kind, copy.deepcopy(_get(vr.out, kind, nm)))
            q1 = any(w.startswith("Q1") for w in vr.warnings) and q1_rounds == 0
            if not vr.flags and not vr.hints and not q1:
                res.stop_reason = "correct"
                break
            only_fc = (
                vr.flags and not vr.hints and not q1 and all(f.rule[0] in "FC" for f in vr.flags)
            )
            if only_fc and len({(f.where, f.idx) for f in vr.flags}) <= cfg.drop_max:
                res.stop_reason = "dropped_few"
                break
            if (
                it == cfg.max_iterations
                or res.calls >= cfg.per_section_call_budget
                or (cfg.stop_after_regen is not None and regen >= cfg.stop_after_regen)
            ):
                res.stop_reason = (
                    "max_iterations"
                    if it == cfg.max_iterations
                    else "budget"
                    if res.calls >= cfg.per_section_call_budget
                    else "regen_limit"
                )
                break
            for h in vr.hints:
                if h.key not in hints:
                    hints[h.key] = h
                    h.hint_id = f"h{len(hints)}"
            open_hints = [h for k, h in hints.items() if k not in rejected_keys]
            if q1:
                q1_rounds += 1
            corrections = render_corrections(
                vr.flags + ([_q1_flag(vr)] if q1 else []), open_hints, cfg
            )
            try:
                new_out = self._call(
                    sec,
                    paras,
                    cards,
                    lexicon,
                    pass_a=False,
                    terms=terms,
                    corrections=corrections,
                    corrective=cfg.bank_corrective,
                )
            except BudgetExceededError:
                raise
            except Exception as e:  # noqa: BLE001
                res.error = f"{type(e).__name__}: {str(e)[:200]}"
                res.stop_reason = "error"
                break
            res.calls += 1
            regen += 1
            for r in new_out["hint_responses"]:
                h = next((x for x in hints.values() if x.hint_id == r["hint_id"]), None)
                if h is None:
                    continue
                if r["decision"] == "rejected" and not cfg.hints_forced:
                    rejected_keys.add(h.key)
                    res.rejected_hints.append(
                        {
                            "hint_id": h.hint_id,
                            "rule": h.rule,
                            "text": h.text,
                            "reason": r["reason"],
                        }
                    )
                    res.hints_rejected += 1
                elif r["decision"] == "added":
                    res.hints_added += 1
            if cfg.carry_forward:
                new_out, n = _carry_forward(new_out, clean, rejected_keys)
                res.restored += n
            sig = json.dumps(new_out, sort_keys=True)
            if sig == prev_sig or sig == json.dumps(out, sort_keys=True):
                out = new_out
                res.stop_reason = "no_change"
                res.iterations.append(
                    {
                        "iteration": it + 1,
                        "output": new_out,
                        "verified": new_out,
                        "flags": [],
                        "hints": [],
                        "autofixes": [],
                        "warnings": ["no change"],
                    }
                )
                last_vr = verify(out, vctx)
                last_vr = self._filter(last_vr, cfg, q1_rounds + 1)
                break
            prev_sig = json.dumps(out, sort_keys=True)
            out = new_out
        # after stopping: drop remaining F/C flags (rule id logged), list unresolved hints
        assert last_vr is not None
        final, dropped = drop_flagged(last_vr.out, last_vr.flags)
        res.rejected = dropped
        res.final = final
        res.unconfirmed_mentions = [h.text for h in last_vr.hints if h.rule == "M1"]
        res.unresolved_hints = [
            {"rule": h.rule, "text": h.text, "detail": h.detail}
            for h in last_vr.hints
            if h.rule != "M1"
        ]
        return res

    @staticmethod
    def _filter(vr: VerifyResult, cfg: LoopConfig, q1_rounds: int) -> VerifyResult:
        if cfg.rules == "sac":  # SAC-KG's own checks only: quantity and format F1-F3
            vr.flags = [f for f in vr.flags if f.rule in {"F1", "F2", "F3"}]
            vr.hints = []
        else:
            vr.hints = [h for h in vr.hints if h.rule in cfg.hint_rules]
        if q1_rounds >= 1:
            vr.warnings = [
                w.replace("Q1:", "Q1 (warning only):", 1) if w.startswith("Q1:") else w
                for w in vr.warnings
            ]
        return vr


def _q1_flag(vr: VerifyResult):
    from cumap.concepts_v4.verifier import Flag

    return Flag(
        "Q1", "section", 0, next((w for w in vr.warnings if w.startswith("Q1")), "too few items")
    )


def _item_keys(out: dict):
    for m in out["existing_mentions"]:
        yield "existing_mentions", m["node_id"], m["node_id"] + "|" + m["surface"].lower()
    for c in out["new_concepts"]:
        yield "new_concepts", c["name"], c["name"].lower()


def _get(out: dict, kind: str, nm: str) -> dict:
    for it in out[kind]:
        k = (
            (it["node_id"] + "|" + it["surface"].lower())
            if kind == "existing_mentions"
            else it["name"].lower()
        )
        if k == nm:
            return it
    raise KeyError(nm)


def _idx(out: dict, kind: str, nm: str) -> int:
    for i, it in enumerate(out[kind]):
        k = (
            (it["node_id"] + "|" + it["surface"].lower())
            if kind == "existing_mentions"
            else it["name"].lower()
        )
        if k == nm:
            return i
    return -1


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def _carry_forward(new_out: dict, clean: dict, rejected_keys: set) -> tuple[dict, int]:
    """Restore an item that passed every rule earlier and disappeared without a rejection, unless its span
    overlaps an item in the latest output (the model may have replaced a partial span itself)."""
    out = copy.deepcopy(new_out)
    present = {(k, nm) for k, _key, nm in _item_keys(out)}
    spans = [_words(c["name"]) for c in out["new_concepts"]] + [
        _words(m["surface"]) for m in out["existing_mentions"]
    ]
    rejected_names = {t for _r, t in rejected_keys}
    n = 0
    for (kind, nm), (_k, item) in clean.items():
        if (kind, nm) in present or nm.split("|")[-1] in rejected_names:
            continue
        iw = _words(item["name"] if kind == "new_concepts" else item["surface"])
        if any(iw & sp for sp in spans):
            continue
        out[kind].append(item)
        n += 1
    return out, n
