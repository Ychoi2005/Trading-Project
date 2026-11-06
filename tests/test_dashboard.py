from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app" / "main.py"
PAGES = [
    "Executive Overview",
    "Market Simulation",
    "Policy Comparison",
    "Scenario Stress Testing",
    "Decision Explorer",
    "Product Insights",
    "Methodology & Limitations",
]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception
    assert not app.error
    assert any(x.value == page for x in app.subheader)


def test_comparison_run_then_insights_and_configuration_change():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Policy Comparison").run()
    app.button[0].click().run()
    assert not app.exception
    assert len(app.dataframe) >= 2
    app.sidebar.radio[0].set_value("Product Insights").run()
    assert not app.exception
    assert any("Completion —" in x.value for x in app.markdown)
    app.sidebar.radio[0].set_value("Policy Comparison").run()
    next(x for x in app.sidebar.select_slider if x.label == "Data latency (ms)").set_value(
        500
    ).run()
    assert any("Configuration changed" in x.value for x in app.warning)
    app.button[0].click().run()
    assert not app.exception


def test_stress_heatmap_and_decision_explorer():
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.sidebar.radio[0].set_value("Scenario Stress Testing").run()
    next(x for x in app.selectbox if x.label == "Stress suite").set_value("heatmap").run()
    app.button[0].click().run()
    assert not app.exception
    assert not app.error
    assert len(app.get("plotly_chart")) >= 4
    app.sidebar.radio[0].set_value("Decision Explorer").run()
    next(x for x in app.selectbox if x.label == "Policy to inspect").set_value(
        "Wait for Fresh Data"
    ).run()
    assert not app.exception
    assert any("Information available at decision time" in x.value for x in app.markdown)


def test_all_missing_wait_trace_and_no_fill_summary():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    next(x for x in app.sidebar.slider if x.label == "Missing-update probability").set_value(
        1.0
    ).run()
    next(
        x for x in app.sidebar.number_input if x.label == "Base liquidity (shares/side)"
    ).set_value(0.0).run()
    app.sidebar.radio[0].set_value("Policy Comparison").run()
    app.button[0].click().run()
    assert not app.exception
    assert any("No orders filled" in x.value for x in app.info)
    app.sidebar.radio[0].set_value("Decision Explorer").run()
    next(x for x in app.selectbox if x.label == "Policy to inspect").set_value(
        "Wait for Fresh Data"
    ).run()
    assert not app.exception
    assert any(x.value == "Unavailable" for x in app.metric)


def test_policy_selection_limits_experiment():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Policy Comparison").run()
    app.multiselect[0].set_value(["Always Execute"]).run()
    app.button[0].click().run()
    assert not app.exception
    result = app.session_state["latest_evidence"]
    assert result.records.policy.unique().tolist() == ["Always Execute"]
    assert len(result.records) == 10


def test_demo_diagnosis_and_healthy_baseline_switch():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert any("Decision intelligence" in x.value for x in app.markdown)
    assert any("older than" in x.value for x in app.warning)
    assert not app.exception
    next(x for x in app.sidebar.selectbox if x.label == "Scenario preset").set_value(
        "Healthy-market baseline"
    ).run()
    assert not app.exception
    assert any("identical" in x.value for x in app.markdown)
    app.button[0].click().run()
    assert app.sidebar.radio[0].value == "Policy Comparison"


def test_insights_flags_outdated_evidence_instead_of_silent_reuse():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Policy Comparison").run()
    app.button[0].click().run()
    app.sidebar.radio[0].set_value("Product Insights").run()
    assert any("CURRENT EVIDENCE" in x.value for x in app.success)
    next(x for x in app.sidebar.select_slider if x.label == "Data latency (ms)").set_value(
        500
    ).run()
    assert any("OUTDATED RESULTS" in x.value for x in app.warning)
    assert not app.exception


def test_market_and_explorer_have_hoverable_action_charts():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Market Simulation").run()
    assert not app.exception
    assert len(app.get("plotly_chart")) >= 4
    app.sidebar.radio[0].set_value("Decision Explorer").run()
    next(x for x in app.selectbox if x.label == "Policy to inspect").set_value(
        "Wait for Fresh Data"
    ).run()
    assert len(app.get("plotly_chart")) == 2
    assert not app.exception
