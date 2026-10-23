import pytest
from pydantic import ValidationError

from cumap.organisation.config import OrgConfig, load_config


def test_default_config_loads_and_hash_is_stable():
    cfg = load_config()
    assert cfg.importance.components["pagerank"].weight == 0.35
    assert sum(c.weight for c in cfg.importance.components.values()) == pytest.approx(1.0)
    assert cfg.rings.shares["centre"] == 0.05 and cfg.null_model.iterations == 200
    assert cfg.config_hash() == load_config().config_hash()


def test_weights_must_sum_to_one():
    raw = load_config().model_dump()
    raw["importance"]["components"]["pagerank"]["weight"] = 0.5
    with pytest.raises(ValidationError):
        OrgConfig(**raw)


def test_ring_shares_must_sum_to_one_and_cover_all_rings():
    raw = load_config().model_dump()
    raw["rings"]["shares"]["outer"] = 0.6
    with pytest.raises(ValidationError):
        OrgConfig(**raw)
