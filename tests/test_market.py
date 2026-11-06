import math

import numpy as np
import pytest

from marketlens.config import MarketConfig, Regime
from marketlens.market import MS_PER_YEAR, simulate_market


def test_seed_replay_and_distinct_paths():
    a = simulate_market(MarketConfig())
    assert a == simulate_market(MarketConfig())
    assert a != simulate_market(MarketConfig(seed=43))


@pytest.mark.parametrize("regime", list(Regime))
def test_quotes_and_regime_parameters(regime):
    config = MarketConfig(regime=regime)
    path = simulate_market(config)
    assert len(path) == 201
    assert path[0].event_time_ms == 0
    assert path[-1].event_time_ms == config.duration_ms
    for i, event in enumerate(path):
        assert event.event_id == i
        assert 0 < event.bid <= event.mid <= event.ask
        assert event.ask - event.bid == pytest.approx(config.effective_spread)
        assert event.spread == config.effective_spread
        assert event.ask_liquidity == config.effective_liquidity


def test_exact_gbm_step_and_annual_units():
    config = MarketConfig(duration_ms=100, step_ms=100, drift=0.03, volatility=0.7)
    z = np.random.default_rng(42).standard_normal()
    dt = 100 / MS_PER_YEAR
    expected = 100 * math.exp((0.03 - 0.5 * 0.7**2) * dt + 0.7 * math.sqrt(dt) * z)
    assert simulate_market(config)[1].mid == pytest.approx(expected)


def test_zero_volatility_and_zero_liquidity():
    path = simulate_market(MarketConfig(volatility=0, liquidity=0))
    assert all(e.mid == 100 and e.ask_liquidity == 0 for e in path)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(initial_price=0),
        dict(volatility=-1),
        dict(spread=float("nan")),
        dict(step_ms=0),
        dict(duration_ms=51),
        dict(seed=-1),
        dict(liquidity=-1),
        dict(duration_ms=True),
        dict(regime="stable"),
    ],
)
def test_invalid_market_config(kwargs):
    with pytest.raises(ValueError):
        MarketConfig(**kwargs)


def test_degenerate_horizon_and_impossible_prices():
    assert len(simulate_market(MarketConfig(duration_ms=0))) == 1
    with pytest.raises(ValueError, match="bid"):
        simulate_market(MarketConfig(spread=201))
    with pytest.raises(ValueError):
        simulate_market(MarketConfig(volatility=1e10))


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(drift=float("nan")),
        dict(drift=True),
        dict(initial_price="bad"),
        dict(volatility=1e308, regime=Regime.HIGH_VOLATILITY),
        dict(duration_ms=100000100, step_ms=50),
    ],
)
def test_extra_invalid_numeric_inputs(kwargs):
    with pytest.raises(ValueError):
        MarketConfig(**kwargs)


def test_extreme_volatility_raises_instead_of_overflowing():
    with pytest.raises(ValueError, match="GBM"):
        simulate_market(MarketConfig(volatility=1e308))
