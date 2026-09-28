"""CR-001 §8.3 acceptance test: batch and live paths must produce identical cache keys.

There is no actual Batch API submission code yet (deferred until M4/M6 have a real
bulk workload — see docs/DECISIONS.md), so this tests the structural guarantee that
makes that safe to add later: `canonical_input_hash` takes no "batch vs live"
parameter at all, so any code path that ends up with the same
(model, prompt_version, messages, schema_name) is guaranteed the same cache key.
"""

from __future__ import annotations

import inspect

from cumap.llm.cache import canonical_input_hash


def test_identical_inputs_produce_identical_hash_regardless_of_caller():
    messages = [{"role": "user", "content": "extract concepts"}]
    # Simulates two different call sites (a hypothetical live path and a hypothetical
    # batch-result-readback path) computing the key independently from the same inputs.
    live_key = canonical_input_hash("gpt-6-luna", "v1", messages, "ConceptList")
    batch_readback_key = canonical_input_hash("gpt-6-luna", "v1", messages, "ConceptList")
    assert live_key == batch_readback_key


def test_hash_function_has_no_batch_vs_live_parameter():
    """Structural guarantee: nothing about *how* a result was produced can leak into
    the key, because the function signature has no such parameter to pass it through.
    """
    params = set(inspect.signature(canonical_input_hash).parameters)
    assert params == {"model", "prompt_version", "messages", "schema_name"}


def test_message_key_order_does_not_affect_hash():
    a = canonical_input_hash("m", "v1", [{"role": "user", "content": "x"}], "S")
    b = canonical_input_hash("m", "v1", [{"content": "x", "role": "user"}], "S")
    assert a == b


def test_different_model_gives_different_hash():
    messages = [{"role": "user", "content": "x"}]
    a = canonical_input_hash("gpt-6-luna", "v1", messages, "S")
    b = canonical_input_hash("gpt-6-sol", "v1", messages, "S")
    assert a != b
