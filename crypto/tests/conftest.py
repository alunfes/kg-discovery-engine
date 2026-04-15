"""Shared pytest fixtures for crypto KG discovery engine tests."""

import sys
import os
import pytest

# Allow importing crypto.src.* from the tests directory
# The test runner is expected to be invoked from the repo root
# (e.g. `python -m pytest crypto/tests/`).
_root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
if _root not in sys.path:
    sys.path.insert(0, _root)


@pytest.fixture(scope="session")
def synthetic_dataset():
    """A small, deterministic SyntheticDataset (30 minutes, seed=42)."""
    from crypto.src.ingestion.synthetic import SyntheticGenerator
    gen = SyntheticGenerator(seed=42, n_minutes=30)
    return gen.generate()


@pytest.fixture(scope="session")
def market_collections(synthetic_dataset):
    """Per-asset MarketStateCollections extracted from synthetic_dataset."""
    from crypto.src.states.extractor import extract_states
    assets = ["HYPE", "ETH", "BTC", "SOL"]
    return {a: extract_states(synthetic_dataset, a, "test_run") for a in assets}


@pytest.fixture(scope="session")
def full_kg(synthetic_dataset, market_collections):
    """Fully built and merged KGraph for use in rule engine tests."""
    from crypto.src.kg.cross_asset import build_cross_asset_kg
    from crypto.src.kg.microstructure import build_microstructure_kg
    from crypto.src.kg.regime import build_regime_kg
    from crypto.src.operators.ops import align, union
    assets = list(market_collections.keys())

    micro_kgs = [build_microstructure_kg(market_collections[a]) for a in assets]
    regime_kgs = [build_regime_kg(market_collections[a]) for a in assets]
    cross_kg = build_cross_asset_kg(market_collections, dataset=synthetic_dataset)

    merged_micro = micro_kgs[0]
    for kg in micro_kgs[1:]:
        merged_micro = union(merged_micro, kg)
    merged_regime = regime_kgs[0]
    for kg in regime_kgs[1:]:
        merged_regime = union(merged_regime, kg)

    return union(union(merged_micro, cross_kg), merged_regime)
