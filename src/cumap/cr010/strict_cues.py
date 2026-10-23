"""CR-010 STOP 4: the strict cue matcher for the P2 pool (token boundaries, contiguous multiword cues, no standalone
function words, explicit inflection forms). Config: configs/cr010_p2_strict_cue_config.yaml, hashed before sampling."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT

CONFIG_PATH = REPO_ROOT / "configs/cr010_p2_strict_cue_config.yaml"
_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class StrictCueMatcher:
    cues: tuple[
        tuple[frozenset[str], ...], ...
    ]  # each cue: per-position sets of accepted token forms
    names: tuple[str, ...]

    def find(self, sentence: str) -> list[str]:
        """Cues (by inventory name) found as contiguous token sequences inside ONE sentence."""
        toks = tokens(sentence)
        hits = []
        for name, cue in zip(self.names, self.cues, strict=True):
            n = len(cue)
            if any(all(toks[i + j] in cue[j] for j in range(n)) for i in range(len(toks) - n + 1)):
                hits.append(name)
        return hits

    def matches(self, sentences: list[str]) -> bool:
        """A span (a list of sentences) holds a cue if any single sentence does: a cue never crosses a boundary."""
        return any(self.find(s) for s in sentences)


def load_config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def kept_cues(cfg: dict) -> list[str]:
    return sorted([*cfg["keep_single_token"], *cfg["keep_multiword"]])


def build_matcher(cfg: dict | None = None) -> StrictCueMatcher:
    cfg = cfg or load_config()
    forms = {k: frozenset(v) for k, v in cfg["lemma_forms"].items()}
    names = kept_cues(cfg)
    cues = tuple(tuple(forms.get(t, frozenset({t})) for t in tokens(n)) for n in names)
    return StrictCueMatcher(cues=cues, names=tuple(names))


def config_hashes(path: Path = CONFIG_PATH) -> dict[str, str]:
    """File sha256 and a sha256 of the parsed content (immune to comment/whitespace edits)."""
    cfg = load_config(path)
    canon = json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode()
    return {
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "content_sha256": hashlib.sha256(canon).hexdigest(),
    }


def reconcile_with_inventory(cfg: dict, inventory: set[str]) -> dict:
    """The config must account for every repository cue exactly once (kept or removed) and invent none."""
    listed = [
        *cfg["removed_standalone_function_words"],
        *cfg["keep_single_token"],
        *cfg["keep_multiword"],
    ]
    return {
        "unaccounted": sorted(inventory - set(listed)),
        "invented": sorted(set(listed) - inventory),
        "duplicates": sorted({c for c in listed if listed.count(c) > 1}),
    }
