"""Provenance footer + label-source tags (CR-005 §4/§6). Every chart and graph carries a
footer naming the run, prompt versions, model tier and date, plus a *label-source tag*
saying what, if anything, the numbers were checked against. A chart without a valid tag
cannot be built: the tag is a required argument and is validated here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# key -> text shown in the footer. Four tags: the CR's three plus the 43-merge owner check.
LABEL_SOURCES: dict[str, str] = {
    "gold_face": "FACE gold (crowd-labelled, IIR)",
    "owner_merge_check": "Owner check of 43 merges",
    "owner_spotcheck": "Owner spot-check (n=30)",
    "model_output": "Model output, not validated",
}


def require_label_source(tag: str | None) -> str:
    if tag not in LABEL_SOURCES:
        raise ValueError(f"label_source must be one of {sorted(LABEL_SOURCES)}, got {tag!r}")
    return LABEL_SOURCES[tag]


@dataclass(frozen=True)
class Provenance:
    run_id: str
    prompt_versions: dict[str, str] = field(default_factory=dict)
    model_tier: str = "strong"
    model: str = ""
    date: str = ""

    def footer(self, label_source: str) -> str:
        prompts = ", ".join(f"{k} {v}" for k, v in sorted(self.prompt_versions.items()))
        model = f"{self.model_tier} ({self.model})" if self.model else self.model_tier
        return (
            f"run {self.run_id} · prompts: {prompts or 'n/a'} · model: {model} · "
            f"{self.date} · labels: {require_label_source(label_source)}"
        )
