import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from marketlens.config import FaultConfig, MarketConfig, OrderConfig
from marketlens.experiments import Scenario, run_experiment, scenario_suite
from marketlens.metrics import mean_interval, penalty_sensitivity
from marketlens.policies import AlwaysExecute
from marketlens.reporting import export_result, scenarios_from_manifest


def test_reproducibility_and_matched_scenarios():
    scenarios = scenario_suite("latency")[:2]
    a = run_experiment(scenarios, (10, 11, 12))
    b = run_experiment(scenarios, (10, 11, 12))
    pd.testing.assert_frame_equal(a.records, b.records)
    pd.testing.assert_frame_equal(a.summary, b.summary)
    assert len(a.records) == 2 * 3 * 4
    for _, group in a.records.groupby(["scenario", "seed"]):
        assert group.path_id.nunique() == 1
        assert group.benchmark_price.nunique() == 1
        assert group.fault_seed.nunique() == 1
        assert len(group) == 4
    # Identical price paths across a latency sweep, not just across policies.
    assert a.records.groupby("seed").path_id.nunique().eq(1).all()


def test_statistics_from_actual_samples():
    low, high = mean_interval([1, 2, 3])
    margin = stats.t.ppf(0.975, 2) / np.sqrt(3)
    assert low == pytest.approx(2 - margin)
    assert high == pytest.approx(2 + margin)
    assert mean_interval([1]) == (None, None)
    assert mean_interval([2, 2]) == (2, 2)


def test_no_fills_not_zero_cost_success_and_penalty_sensitivity():
    scenario = Scenario(
        faults=FaultConfig(missing_probability=1), market=MarketConfig(liquidity=0, volatility=0)
    )
    result = run_experiment((scenario,), (1, 2))
    assert not result.records.filled.any()
    assert result.summary.mean_shortfall.isna().all()
    assert result.summary.completion_rate.eq(0).all()
    assert result.records.penalized_cost.eq(10).all()
    sensitivity = penalty_sensitivity(result.records, (0, 1))
    assert sensitivity[sensitivity.penalty_per_share == 1].mean_cost.eq(100).all()
    assert sensitivity[sensitivity.penalty_per_share == 0].mean_cost.eq(0).all()


def test_paired_differences_and_conditional_cost_metrics():
    result = run_experiment((Scenario(),), (1, 2, 3))
    assert result.summary.completion_rate.eq(1).all()
    assert result.paired.pairs.eq(3).all()
    assert result.paired.mean_cost_difference.eq(0).all()
    for _, row in result.summary.iterrows():
        actual = result.records[result.records.policy == row.policy].implementation_shortfall
        assert row.mean_shortfall == pytest.approx(actual.mean())
        assert row.std_shortfall == pytest.approx(actual.std())
        assert row.p95_shortfall == pytest.approx(actual.quantile(0.95))


def test_export_and_manifest_replay(tmp_path):
    original = run_experiment(scenario_suite("combined"), (20, 21))
    export_result(original, tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["software"]["numpy"]
    replay = run_experiment(
        scenarios_from_manifest(manifest), manifest["seeds"], manifest["penalty_per_share"]
    )
    pd.testing.assert_frame_equal(original.records, replay.records)
    loaded = pd.read_csv(tmp_path / "records.csv")
    assert len(loaded) == len(original.records)
    assert loaded.path_id.tolist() == original.records.path_id.tolist()
    assert set(p.name for p in tmp_path.iterdir()) == {
        "records.csv",
        "summary.csv",
        "paired.csv",
        "sensitivity.csv",
        "manifest.json",
    }


@pytest.mark.parametrize(
    "kind,count",
    [
        ("latency", 6),
        ("missing", 5),
        ("volatility", 3),
        ("liquidity", 4),
        ("combined", 2),
        ("thresholds", 9),
        ("heatmap", 9),
    ],
)
def test_suites_execute(kind, count):
    base = Scenario(
        market=MarketConfig(duration_ms=2000), order=OrderConfig(arrival_ms=500, deadline_ms=1500)
    )
    scenarios = scenario_suite(kind, base)
    assert len(scenarios) == count
    assert len(run_experiment(scenarios, (1,)).records) == count * 4


@pytest.mark.parametrize("seeds", [(), (1, 1), (-1,), (True,)])
def test_invalid_seeds(seeds):
    with pytest.raises(ValueError):
        run_experiment((Scenario(),), seeds)


def test_invalid_experiment_inputs():
    with pytest.raises(ValueError):
        run_experiment((), (1,))
    with pytest.raises(ValueError):
        run_experiment((Scenario(), Scenario()), (1,))
    with pytest.raises(ValueError):
        run_experiment((Scenario(),), (1,), policies=())
    with pytest.raises(ValueError):
        run_experiment((Scenario(),), (1,), policies=(AlwaysExecute(), AlwaysExecute()))
    with pytest.raises(ValueError):
        scenario_suite("unknown")
    with pytest.raises(ValueError):
        replace(Scenario(), name=" ")
    with pytest.raises(ValueError):
        replace(Scenario(), market=MarketConfig(duration_ms=500))
    with pytest.raises(ValueError):
        run_experiment((Scenario(),), (1,), penalty_per_share=-1)


def test_policy_selection_and_equivalent_observation_interface():
    names = ("Always Execute", "Wait for Fresh Data")
    result = run_experiment((Scenario(),), (42,), policy_names=names)
    assert set(result.records.policy) == set(names)
    assert result.manifest["policy_names"] == list(names)
    with pytest.raises(ValueError):
        run_experiment((Scenario(),), (42,), policy_names=("Unknown policy",))
    with pytest.raises(ValueError):
        run_experiment((Scenario(),), (42,), policy_names=())
    with pytest.raises(ValueError):
        run_experiment((Scenario(),), (42,), policies=(AlwaysExecute(),), policy_names=names)
