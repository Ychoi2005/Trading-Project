from dataclasses import replace

import pytest

from marketlens.config import FaultConfig, Interval, MarketConfig
from marketlens.faults import inject_faults
from marketlens.market import simulate_market
from marketlens.observations import ObservationCursor


@pytest.fixture
def path():
    return simulate_market(MarketConfig(duration_ms=500, step_ms=50))


def test_latency_no_early_delivery(path):
    deliveries = inject_faults(path, FaultConfig(latency_ms=100))
    cursor = ObservationCursor(deliveries)
    assert cursor.at(99).quote is None
    assert cursor.at(100).quote.event_time_ms == 0
    assert cursor.at(150).quote.event_time_ms == 50
    assert deliveries[-1].delivery_time_ms == 600


def test_loss_extremes_replay_and_source_immutability(path):
    original = tuple(path)
    assert len(inject_faults(path, FaultConfig())) == len(path)
    assert inject_faults(path, FaultConfig(missing_probability=1)) == ()
    config = FaultConfig(missing_probability=0.5)
    a = inject_faults(path, config)
    assert a == inject_faults(path, config)
    assert 0 < len(a) < len(path)
    assert path == original


def test_stale_quote_retains_original_timestamp(path):
    ds = inject_faults(path, FaultConfig(stale_intervals=(Interval(50, 200),)))
    cursor = ObservationCursor(ds)
    stale = cursor.at(199)
    assert stale.quote.event_time_ms == 0
    assert stale.quote_age_ms == 199
    assert stale.since_delivery_ms == 199
    fresh = cursor.at(200)
    assert fresh.quote.event_time_ms == 200
    assert fresh.last_sequence_gap == 3


def test_outage_uses_delivery_clock_and_half_open_bounds(path):
    ds = inject_faults(path, FaultConfig(latency_ms=50, outage_intervals=(Interval(100, 200),)))
    assert [d.delivery_time_ms for d in ds][:3] == [50, 200, 250]
    cursor = ObservationCursor(ds)
    assert cursor.at(199).quote.event_time_ms == 0
    assert cursor.at(200).quote.event_time_ms == 150


def test_combined_faults_and_overlapping_intervals(path):
    config = FaultConfig(
        latency_ms=50,
        missing_probability=0.3,
        stale_intervals=(Interval(0, 100), Interval(50, 150)),
        outage_intervals=(Interval(250, 400),),
    )
    ds = inject_faults(path, config)
    for d in ds:
        assert d.quote.event_time_ms >= 150
        assert d.delivery_time_ms == d.quote.event_time_ms + 50
        assert not 250 <= d.delivery_time_ms < 400
    assert ds == inject_faults(path, config)


def test_clock_validation_and_empty_stream(path):
    assert ObservationCursor(()).at(100).quote is None
    cursor = ObservationCursor(inject_faults(path, FaultConfig()))
    cursor.at(100)
    with pytest.raises(ValueError, match="backwards"):
        cursor.at(99)
    with pytest.raises(ValueError):
        inject_faults(tuple(reversed(path)), FaultConfig())
    q = inject_faults(path, FaultConfig())[1].quote
    from marketlens.events import Delivery

    with pytest.raises(ValueError):
        ObservationCursor((Delivery(replace(q, delivery_time_ms=0)),))


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(latency_ms=-1),
        dict(missing_probability=1.1),
        dict(missing_probability=float("nan")),
        dict(stale_intervals=[]),
        dict(seed=True),
    ],
)
def test_invalid_fault_config(kwargs):
    with pytest.raises(ValueError):
        FaultConfig(**kwargs)


def test_invalid_interval():
    with pytest.raises(ValueError):
        Interval(5, 5)
