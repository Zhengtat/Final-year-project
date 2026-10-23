"""CR-008 §3.0 learning loop: owner merge-sheet marks -> lexicon entries that cite their sheet row.

`ok`/`same` -> a `same` entry; `wrong`/`different` -> a `different` entry. Entries derived from
owner marks are `approved` (scope `book:pd6e`). Pairs the owner marked both ways across sheets are
left out and reported (`skipped`). Reads sheets only; never writes `data/gold/`.
"""

from __future__ import annotations

from cumap.expert_kg.alias_rules import AliasConfig, r1_key


def propose_from_marks(
    rows: list[dict], cfg: AliasConfig, *, exclude: set[frozenset[str]] = frozenset()
):
    """rows: dicts with sheet, id, a, b, same (bool), section, quote. -> (entries, skipped)."""
    by_pair: dict[frozenset[str], list[dict]] = {}
    for r in rows:
        by_pair.setdefault(frozenset((r1_key(r["a"], cfg), r1_key(r["b"], cfg))), []).append(r)
    entries, skipped = [], []
    for pair, rs in by_pair.items():
        if pair in exclude or len({r["same"] for r in rs}) > 1:
            skipped.append(rs)
            continue
        r = rs[0]
        cites = ", ".join(f"{x['sheet']} sheet row {x['id']}" for x in rs)
        if r["same"]:
            entries.append(
                {
                    "id": f"S-{r['sheet']}-{r['id']}",
                    "canonical": r["b"],
                    "forms": [r["a"], r["b"]],
                    "scope": "book:pd6e",
                    "status": "approved",
                    "source": f"owner mark: {cites}",
                    "quote": r.get("quote") or None,
                    "section": r.get("section") or None,
                }
            )
        else:
            entries.append(
                {
                    "id": f"D-{r['sheet']}-{r['id']}",
                    "forms": [r["a"], r["b"]],
                    "kind": "confusable",
                    "why": "owner marked these two as different",
                    "distinction_dimension": None,
                    "scope": "book:pd6e",
                    "status": "approved",
                    "source": f"owner mark: {cites}",
                    "quote": r.get("quote") or None,
                    "section": r.get("section") or None,
                }
            )
    return entries, skipped
