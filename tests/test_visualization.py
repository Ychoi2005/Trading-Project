from dataclasses import replace

from marketlens.execution import evaluate_policy
from marketlens.experiments import demonstration_scenario, fault_seed
from marketlens.faults import inject_faults
from marketlens.market import simulate_market
from marketlens.policies import standard_policies
from marketlens.visualization import decision_frame, decision_timeline, price_figure


def sample():
    scenario = demonstration_scenario()
    events = simulate_market(scenario.market)
    ds = inject_faults(events, replace(scenario.faults, seed=fault_seed(42, scenario.faults.seed)))
    results = tuple(
        evaluate_policy(events, ds, p, scenario.order) for p in standard_policies(scenario.policy)
    )
    return scenario, events, ds, results


def test_all_action_markers_have_reasons_and_observed_not_true_prices():
    scenario, events, ds, results = sample()
    frame = decision_frame(results)
    assert set(frame.action) == {"execute", "wait", "pause"}
    assert frame.reason.str.len().gt(0).all()
    timeline = decision_timeline(results)
    assert {t.name for t in timeline.data} == {"Execute", "Wait", "Pause"}
    assert all("Quote age" in t.hovertemplate for t in timeline.data)
    fig = price_figure(events, ds, results, scenario)
    assert fig.data[0].line.dash != fig.data[1].line.dash
    assert "retrospective" in fig.data[0].name
    assert fig.data[1].line.shape == "hv"
    for trace in fig.data[2:]:
        expected = frame[(frame.action.str.title() == trace.name) & frame.observed_mid.notna()]
        assert list(trace.y) == expected.observed_mid.tolist()


def test_changing_truth_changes_only_the_retrospective_price_trace():
    scenario, events, ds, results = sample()
    a = price_figure(events, ds, results, scenario)
    changed = tuple(replace(e, mid=e.mid + 1, bid=e.bid + 1, ask=e.ask + 1) for e in events)
    b = price_figure(changed, ds, results, scenario)
    assert list(a.data[0].y) != list(b.data[0].y)
    for left, right in zip(a.data[1:], b.data[1:], strict=True):
        assert list(left.y) == list(right.y)
