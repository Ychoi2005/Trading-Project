from dataclasses import replace

import pytest

from marketlens.config import FaultConfig, Interval, MarketConfig, OrderConfig, PolicyConfig
from marketlens.execution import evaluate_policy
from marketlens.faults import inject_faults
from marketlens.market import simulate_market
from marketlens.observations import Observation, ObservationCursor
from marketlens.policies import (
    Action,
    AdaptiveDecisionPolicy,
    AlwaysExecute,
    DataQualityGuardrail,
    WaitForFreshData,
)


def test_policy_thresholds():
    path = simulate_market(MarketConfig())
    q = inject_faults(path, FaultConfig())[0].quote
    cfg = PolicyConfig(freshness_ms=100, max_wait_ms=200, pause_after_ms=300)
    fresh = Observation(100, q, 1, 0)
    old = replace(fresh, time_ms=101)
    assert WaitForFreshData(cfg).decide(fresh, 100).action == Action.EXECUTE
    assert WaitForFreshData(cfg).decide(old, 100).action == Action.WAIT
    assert WaitForFreshData(cfg).decide(old, 200).action == Action.PAUSE
    assert (
        WaitForFreshData(replace(cfg, timeout_execute=True)).decide(old, 200).action
        == Action.EXECUTE
    )
    guard = DataQualityGuardrail(cfg)
    assert guard.decide(old, 0).action == Action.PAUSE
    assert guard.decide(replace(fresh, last_sequence_gap=6), 0).action == Action.PAUSE
    assert guard.decide(replace(fresh, quote=replace(q, spread=1)), 0).action == Action.PAUSE
    assert guard.decide(fresh, 0).action == Action.EXECUTE
    assert guard.decide(Observation(0, None, 0, 0), 0).action == Action.PAUSE


def test_adaptive_rules_and_unconditional_baseline():
    empty = Observation(0, None, 0, 0)
    cfg = PolicyConfig(max_wait_ms=200, pause_after_ms=100)
    adaptive = AdaptiveDecisionPolicy(cfg)
    assert adaptive.decide(empty, 0).action == Action.WAIT
    assert adaptive.decide(empty, 100).action == Action.PAUSE
    assert adaptive.decide(empty, 200).action == Action.PAUSE
    assert AlwaysExecute().decide(empty, 0).action == Action.EXECUTE


def test_no_lookahead_and_exact_timeout():
    path = simulate_market(MarketConfig())
    ds = inject_faults(path, FaultConfig(outage_intervals=(Interval(0, 2000),)))
    result = evaluate_policy(
        path,
        ds,
        WaitForFreshData(PolicyConfig(max_wait_ms=125)),
        OrderConfig(),
        decision_step_ms=100,
    )
    assert result.fill is None
    assert result.end_time_ms == 1125
    assert all(t.observation.quote is None for t in result.trace)
    assert not hasattr(result.trace[0].observation, "ground_truth")
    # Changing all future quotes cannot change an earlier policy decision.
    cursor = ObservationCursor(ds)
    obs = cursor.at(1000)
    altered = tuple(replace(d, quote=replace(d.quote, mid=999)) for d in ds)
    assert obs == ObservationCursor(altered).at(1000)
    assert WaitForFreshData().decide(obs, 0) == WaitForFreshData().decide(
        ObservationCursor(altered).at(1000), 0
    )


def test_wait_executes_on_first_eligible_delivery():
    path = simulate_market(MarketConfig())
    ds = inject_faults(path, FaultConfig(outage_intervals=(Interval(0, 1200),)))
    result = evaluate_policy(path, ds, WaitForFreshData(), OrderConfig())
    assert result.fill.time_ms == 1200
    assert result.execution_delay_ms == 200
    for trace in result.trace:
        quote = trace.observation.quote
        assert quote is None or quote.delivery_time_ms <= trace.observation.time_ms


def test_adaptive_silence_boundary():
    path = simulate_market(MarketConfig())
    q = inject_faults(path, FaultConfig())[0].quote
    cfg = PolicyConfig(freshness_ms=0, max_wait_ms=500, pause_after_ms=100)
    assert AdaptiveDecisionPolicy(cfg).decide(Observation(99, q, 1, 0), 0).action == Action.WAIT
    assert AdaptiveDecisionPolicy(cfg).decide(Observation(100, q, 1, 0), 0).action == Action.PAUSE


@pytest.mark.parametrize(
    "kwargs",
    [dict(max_wait_ms=-1), dict(freshness_ms=True), dict(max_spread=-1), dict(timeout_execute=1)],
)
def test_invalid_policy_config(kwargs):
    with pytest.raises(ValueError):
        PolicyConfig(**kwargs)


def test_all_policies_receive_identical_initial_information():
    from marketlens.policies import standard_policies

    path = simulate_market(MarketConfig())
    ds = inject_faults(path, FaultConfig(latency_ms=250, missing_probability=0.3))
    outcomes = [evaluate_policy(path, ds, p, OrderConfig()) for p in standard_policies()]
    assert all(r.trace[0].observation == outcomes[0].trace[0].observation for r in outcomes)


def test_future_truth_changes_cannot_affect_decisions():
    path = simulate_market(MarketConfig())
    ds = inject_faults(path, FaultConfig(latency_ms=500))
    altered = tuple(
        replace(e, mid=e.mid + 50, bid=e.bid + 50, ask=e.ask + 50) if e.event_time_ms >= 1000 else e
        for e in path
    )
    policy = WaitForFreshData(PolicyConfig(freshness_ms=100, max_wait_ms=200))
    first = evaluate_policy(path, ds, policy, OrderConfig())
    second = evaluate_policy(altered, ds, policy, OrderConfig())
    assert first.trace == second.trace
