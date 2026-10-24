"""CR-053: SciNLP generator prompt v5_scinlp through profile v3 (no network, no key)."""

import yaml

from cumap.config import REPO_ROOT
from cumap.llm.prompts import load_prompt


def test_v5_differs_from_v4_only_in_definitions_and_v4_is_untouched():
    v4 = load_prompt(REPO_ROOT / "prompts", "concept_generator", "v4_scinlp").body
    v5 = load_prompt(REPO_ROOT / "prompts", "concept_generator", "v5_scinlp").body
    assert "Evaluation measures are always concepts" in v5 and "Evaluation measures" not in v4
    for part in ("=== PROCEDURE ===", "=== OUTPUT SCHEMA ===", "=== THIS SECTION ==="):
        assert v4[v4.index(part) :] == v5[v5.index(part) :]


def test_profile_v3_is_v2_with_the_new_prompt_and_the_default_runner():
    p2 = yaml.safe_load((REPO_ROOT / "configs/scinlp_profile_v2.yaml").read_text())
    p3 = yaml.safe_load((REPO_ROOT / "configs/scinlp_profile_v3.yaml").read_text())
    assert p3["generator_prompt"]["version"] == "v5_scinlp"
    assert {k: v for k, v in p3.items() if k not in ("generator_prompt", "status")} == {
        k: v for k, v in p2.items() if k not in ("generator_prompt", "status")
    }
    assert 'default="cumap.cr053.scinlp_run"' in (REPO_ROOT / "src/cumap/cr043/run.py").read_text()
