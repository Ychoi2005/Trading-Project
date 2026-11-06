from dataclasses import replace

import pandas as pd
import pytest

from marketlens.config import FaultConfig, Interval, MarketConfig, OrderConfig, PolicyConfig
from marketlens.execution import evaluate_policy
from marketlens.experiments import demonstration_scenario, healthy_scenario, run_experiment
from marketlens.faults import inject_faults
from marketlens.intelligence import comparison_insights, exposure_metrics, scenario_diagnosis
from marketlens.market import simulate_market
from marketlens.metrics import joint_fill_comparisons
from marketlens.policies import AlwaysExecute, WaitForFreshData


def test_demo_has_distinct_actions_without_assuming_cost_superiority():
    demo = demonstration_scenario()
    assert demo.market.volatility > healthy_scenario().market.volatility
    assert demo.faults.latency_ms > 0 and demo.faults.missing_probability > 0
    result = run_experiment((demo,), (42,))
    rows = result.records.set_index("policy")
    assert rows.loc["Always Execute", "execution_delay_ms"] == 0
    assert rows.loc["Wait for Fresh Data", "execution_delay_ms"] > 0
    assert not rows.loc["Data Quality Guardrail", "filled"]
    assert rows.loc["Adaptive Decision Policy", "execution_delay_ms"] > 0
    assert rows.loc["Always Execute", "executed_on_stale_quote"]
    assert not rows.loc["Wait for Fresh Data", "executed_on_stale_quote"]
    assert rows.path_id.nunique() == 1
    pd.testing.assert_frame_equal(result.records, run_experiment((demo,), (42,)).records)


def test_healthy_ties_explained_and_no_universal_winner_claimed():
    result = run_experiment((healthy_scenario(),), (42, 43))
    messages = comparison_insights(result.records)
    assert any("identical" in text for text in messages)
    assert any("No universal winner" in text for text in messages)
    assert result.summary.stale_fill_rate.eq(0).all()


def test_time_weighted_exposure_counts_silence_and_threshold_crossings():
    path = simulate_market(MarketConfig(duration_ms=2000))
    quote0 = inject_faults(path[:1], FaultConfig())
    policy = WaitForFreshData(PolicyConfig(freshness_ms=100, max_wait_ms=375))
    outcome = evaluate_policy(
        path, quote0, policy, OrderConfig(arrival_ms=50, deadline_ms=1000), 80
    )
    # First quote is fresh, so it executes at arrival with no pending duration.
    metrics = exposure_metrics(outcome, 100)
    assert metrics["pending_duration_ms"] == 0
    assert metrics["pending_stale_fraction"] is None
    # At arrival 150 the held quote is stale throughout the 375 ms wait.
    outcome = evaluate_policy(
        path, quote0, policy, OrderConfig(arrival_ms=150, deadline_ms=1000), 80
    )
    metrics = exposure_metrics(outcome, 100)
    assert metrics["pending_stale_ms"] == 375
    assert metrics["pending_stale_fraction"] == 1
    empty = evaluate_policy(path, (), policy, OrderConfig(arrival_ms=150, deadline_ms=1000), 80)
    metrics = exposure_metrics(empty, 100)
    assert metrics["pending_unavailable_ms"] == 375
    assert metrics["pending_stale_ms"] == 0


def test_threshold_crossing_between_irregular_decisions():
    # Wait because spread is too wide, even though quote initially meets its age limit.
    from marketlens.policies import AdaptiveDecisionPolicy

    path = simulate_market(MarketConfig(duration_ms=2000, spread=0.2))
    ds = inject_faults(path[:1], FaultConfig())
    p = AdaptiveDecisionPolicy(PolicyConfig(freshness_ms=100, max_wait_ms=200, pause_after_ms=1000))
    out = evaluate_policy(path, ds, p, OrderConfig(arrival_ms=50, deadline_ms=1000), 80)
    metrics = exposure_metrics(out, 100)
    assert metrics["pending_duration_ms"] == 200
    assert metrics["pending_stale_ms"] == 150  # [100,250), not a tick-count average
    assert metrics["pending_stale_fraction"] == 0.75


def test_joint_fill_analysis_does_not_count_unfilled_as_free_fills():
    result = run_experiment((demonstration_scenario(),), tuple(range(42, 47)))
    joint = joint_fill_comparisons(result.records).set_index("policy")
    assert joint.loc["Data Quality Guardrail", "joint_fills"] == 0
    assert pd.isna(joint.loc["Data Quality Guardrail", "mean_difference"])
    assert joint.loc["Wait for Fresh Data", "joint_fills"] > 0
    assert all(joint.lower_cost_pairs + joint.higher_cost_pairs <= joint.joint_fills)
    one = run_experiment((healthy_scenario(),), (1,))
    assert joint_fill_comparisons(one.records).ci_low.isna().all()


def test_diagnosis_separates_suppression_from_in_flight_data():
    path = simulate_market(MarketConfig(duration_ms=200))
    ds = inject_faults(path, FaultConfig(latency_ms=100))
    diagnosis = scenario_diagnosis(path, ds, 50)
    assert diagnosis["suppressed_updates"] == 0
    assert diagnosis["in_flight_after_horizon"] == 2
    assert diagnosis["delivered_by_horizon"] == 3
    assert diagnosis["unavailable_grid_fraction"] == pytest.approx(2 / 5)


def test_all_missing_and_no_baseline_insights_are_truthful():
    scenario = replace(demonstration_scenario(), faults=FaultConfig(missing_probability=1))
    result = run_experiment((scenario,), (42,), policy_names=("Wait for Fresh Data",))
    assert any("No orders filled" in m for m in comparison_insights(result.records))
    assert joint_fill_comparisons(result.records).empty
    baseline = run_experiment((scenario,), (42,), policies=(AlwaysExecute(),))
    assert baseline.records.executed_without_quote.all()


def test_exposure_has_no_truth_dependency():
    path = simulate_market(MarketConfig())
    ds = inject_faults(path, FaultConfig(outage_intervals=(Interval(0, 1200),)))
    policy = WaitForFreshData()
    a = evaluate_policy(path, ds, policy, OrderConfig())
    altered = tuple(replace(e, mid=e.mid + 1, bid=e.bid + 1, ask=e.ask + 1) for e in path)
    b = evaluate_policy(altered, ds, policy, OrderConfig())
    assert a.trace == b.trace
    assert exposure_metrics(a, 100) == exposure_metrics(b, 100)
