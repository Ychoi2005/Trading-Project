"""Interactive research UI; every displayed result is produced by the engines."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from marketlens.config import FaultConfig, Interval, MarketConfig, OrderConfig, PolicyConfig, Regime
from marketlens.execution import evaluate_policy
from marketlens.experiments import (
    Scenario,
    demonstration_scenario,
    fault_seed,
    healthy_scenario,
    run_experiment,
    scenario_suite,
)
from marketlens.faults import inject_faults
from marketlens.intelligence import (
    comparison_insights,
    exposure_metrics,
    reliability_frame,
    scenario_diagnosis,
)
from marketlens.market import simulate_market
from marketlens.metrics import joint_fill_comparisons
from marketlens.policies import standard_policies
from marketlens.reporting import reproducibility_manifest
from marketlens.visualization import decision_frame, decision_timeline, price_figure

PAGES = (
    "Executive Overview",
    "Market Simulation",
    "Policy Comparison",
    "Scenario Stress Testing",
    "Decision Explorer",
    "Product Insights",
    "Methodology & Limitations",
)
COLORS = ["#2dd4bf", "#60a5fa", "#c4b5fd", "#fbbf24"]


@st.cache_data(show_spinner=False)
def sample(scenario: Scenario):
    events = simulate_market(scenario.market)
    ds = inject_faults(
        events,
        replace(scenario.faults, seed=fault_seed(scenario.market.seed, scenario.faults.seed)),
    )
    results = tuple(
        evaluate_policy(events, ds, p, scenario.order, scenario.decision_step_ms)
        for p in standard_policies(scenario.policy)
    )
    return events, ds, results


@st.cache_data(show_spinner=False, max_entries=12)
def experiment(
    scenarios: tuple[Scenario, ...],
    seeds: tuple[int, ...],
    penalty: float,
    policy_names: tuple[str, ...] | None = None,
):
    return run_experiment(scenarios, seeds, penalty, policy_names=policy_names)


def chart(fig, key: str) -> None:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e6edf5",
        margin=dict(l=20, r=20, t=40, b=20),
        legend_title_text="",
    )
    if len(fig.data) == 1:
        fig.update_layout(showlegend=False)
    labels = {
        "completion_rate": "Completion rate",
        "mean_shortfall": "Shortfall ($/order)",
        "average_delay_ms": "Delay (ms)",
        "non_execution_rate": "Non-execution rate",
        "stale_fill_rate": "Fraction of fills",
        "pending_stale_fraction": "Fraction of pending time",
        "penalty_per_share": "Assumed penalty ($/share)",
        "mean_cost": "Adjusted cost ($/order)",
    }
    for axis in fig.select_xaxes():
        if axis.title.text == "policy":
            axis.title.text = None
        elif axis.title.text in labels:
            axis.title.text = labels[axis.title.text]
    for axis in fig.select_yaxes():
        if axis.title.text in labels:
            axis.title.text = labels[axis.title.text]
    st.plotly_chart(fig, width="stretch", key=key)


def controls() -> tuple[Scenario, int, float]:
    with st.sidebar:
        st.markdown("### Experiment setup")
        selected = st.selectbox(
            "Scenario preset", ["Reliability stress demonstration", "Healthy-market baseline"]
        )
        base = (
            demonstration_scenario() if selected.startswith("Reliability") else healthy_scenario()
        )
        st.caption("Preset starting point · controls below can override its assumptions.")

        def widget_key(name: str) -> str:
            return f"{selected}:{name}"

        seed = st.number_input(
            "Random seed",
            min_value=0,
            max_value=1_000_000,
            value=42,
            step=1,
            key=widget_key("seed"),
        )
        with st.expander("Market & feed conditions"):
            regime = st.selectbox(
                "Market regime",
                list(Regime),
                format_func=lambda x: x.value,
                key=widget_key("regime"),
            )
            volatility = st.slider(
                "Annualised volatility",
                0.0,
                3.0,
                base.market.volatility,
                0.05,
                key=widget_key("volatility"),
            )
            liquidity = st.number_input(
                "Base liquidity (shares/side)", 0.0, 100000.0, 1000.0, key=widget_key("liquidity")
            )
            spread = st.number_input(
                "Base spread ($/share)", 0.0, 1.0, 0.02, 0.01, key=widget_key("spread")
            )
            latency = st.select_slider(
                "Data latency (ms)",
                [0, 50, 100, 250, 500, 1000],
                value=base.faults.latency_ms,
                key=widget_key("latency"),
            )
            missing = st.slider(
                "Missing-update probability",
                0.0,
                1.0,
                base.faults.missing_probability,
                0.05,
                key=widget_key("missing"),
            )
        with st.expander("Order & policy limits"):
            quantity = st.number_input(
                "Order quantity (shares)", 1.0, 100000.0, 100.0, key=widget_key("quantity")
            )
            freshness = st.number_input(
                "Freshness threshold (ms)",
                0,
                10000,
                base.policy.freshness_ms,
                step=50,
                key=widget_key("fresh"),
            )
            wait = st.number_input(
                "Maximum wait (ms)",
                0,
                10000,
                base.policy.max_wait_ms,
                step=50,
                key=widget_key("wait"),
            )
            silence = st.number_input(
                "Pause after delivery silence (ms)",
                0,
                10000,
                base.policy.pause_after_ms,
                step=50,
                key=widget_key("silence"),
            )
            max_spread = st.number_input(
                "Maximum observed spread ($/share)", 0.0, 10.0, 0.1, key=widget_key("maxspread")
            )
            max_gap = st.number_input(
                "Maximum last observed sequence gap",
                0,
                10000,
                base.policy.max_sequence_gap,
                key=widget_key("gap"),
            )
            timeout = st.checkbox(
                "Wait policy executes at timeout", value=False, key=widget_key("timeout")
            )
        with st.expander("Advanced timing & costs"):
            seconds = st.slider(
                "Simulation duration (seconds)", 2, 60, 10, key=widget_key("seconds")
            )
            horizon = seconds * 1000
            step = st.selectbox(
                "Market time step (ms)", [10, 50, 100], index=1, key=widget_key("step")
            )
            arrival = st.slider(
                "Order arrival (ms)",
                0,
                horizon,
                min(1000, horizon),
                step=50,
                key=widget_key("arrival"),
            )
            deadline = st.slider(
                "Execution deadline (ms)",
                arrival,
                horizon,
                min(max(5000, arrival), horizon),
                step=50,
                key=widget_key("deadline"),
            )
            price = st.number_input(
                "Initial price ($/share)", min_value=1.0, value=100.0, key=widget_key("price")
            )
            drift = st.number_input(
                "Annualised drift", value=0.0, step=0.01, key=widget_key("drift")
            )
            fee = st.number_input(
                "Fee ($/share)", 0.0, 1.0, 0.001, step=0.001, format="%.3f", key=widget_key("fee")
            )
            impact = st.number_input(
                "Impact coefficient ($/share)", 0.0, 10.0, 0.01, key=widget_key("impact")
            )
            reference = st.number_input(
                "Benchmark price (0 = arrival mid)", 0.0, 100000.0, 0.0, key=widget_key("reference")
            )
            outage_start = st.number_input(
                "Outage start (ms)", 0, horizon, min(900, horizon), key=widget_key("outagestart")
            )
            outage_length = st.number_input(
                "Outage duration (ms)",
                0,
                horizon,
                300 if base.faults.outage_intervals else 0,
                step=50,
                key=widget_key("outageduration"),
            )
            stale_start = st.number_input(
                "Stale window start (ms)",
                0,
                horizon,
                min(900, horizon),
                key=widget_key("stalestart"),
            )
            stale_length = st.number_input(
                "Stale window duration (ms)",
                0,
                horizon,
                0,
                step=50,
                key=widget_key("staleduration"),
            )
        with st.expander("Repeated experiments"):
            preview = st.checkbox("Preview mode (10 trials)", value=True)
            trials = st.number_input("Full trial count", 2, 1000, 100, step=10)
            penalty = st.number_input("Non-execution penalty ($/share)", 0.0, 10.0, 0.1)
        st.caption("Synthetic single asset · marketable buys · no real trading connection")
    market = MarketConfig(price, horizon, step, drift, volatility, spread, liquidity, seed, regime)
    faults = FaultConfig(
        latency,
        missing,
        (Interval(stale_start, stale_start + stale_length),) if stale_length else (),
        (Interval(outage_start, outage_start + outage_length),) if outage_length else (),
    )
    order = OrderConfig(arrival, deadline, quantity, fee, impact, reference or None)
    policy = PolicyConfig(freshness, wait, silence, max_spread, max_gap, timeout)
    return (
        Scenario(selected, market, faults, order, policy, step),
        (10 if preview else trials),
        penalty,
    )


def comparison_table(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary[
        [
            "scenario",
            "policy",
            "completion_rate",
            "non_execution_rate",
            "mean_shortfall",
            "average_delay_ms",
            "stale_fill_rate",
            "no_quote_fill_rate",
        ]
    ].copy()
    for column in (
        "completion_rate",
        "non_execution_rate",
        "stale_fill_rate",
        "no_quote_fill_rate",
    ):
        frame[column] *= 100
    return frame.rename(
        columns={
            "scenario": "Scenario",
            "policy": "Policy",
            "completion_rate": "Completion (%)",
            "non_execution_rate": "Unfilled (%)",
            "mean_shortfall": "Mean filled shortfall ($)",
            "average_delay_ms": "Delay (ms)",
            "stale_fill_rate": "Stale quote at fill (%)",
            "no_quote_fill_rate": "No quote at fill (%)",
        }
    )


def overview(scenario: Scenario, events, deliveries, results) -> None:
    st.caption(f"CURRENT SINGLE-PATH RUN · {scenario.name} · seed {scenario.market.seed}")
    st.markdown("### Decision intelligence")
    st.write("What does unreliable information change about this order?")
    diagnosis = scenario_diagnosis(events, deliveries, scenario.policy.freshness_ms)
    first = results[0].trace[0].observation
    a, b, c, d = st.columns(4)
    a.metric("Age at order arrival", f"{first.quote_age_ms} ms" if first.quote else "No quote")
    b.metric("Feed latency", f"{scenario.faults.latency_ms} ms")
    c.metric("Updates suppressed", diagnosis["suppressed_updates"])
    d.metric("Policies completing", f"{sum(r.fill is not None for r in results)}/{len(results)}")
    st.caption(
        "Suppression is a retrospective diagnostic. Quote age is available to the policy; "
        "future loss, outages and true prices are not."
    )
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### 01 · Market & feed diagnosis")
        st.write(
            f"Annualised volatility is {scenario.market.effective_volatility:.0%}; "
            f"the retrospective mid-price range is ${diagnosis['realized_mid_range']:.4f}/share. "
            f"{diagnosis['delivered_by_horizon']} of {diagnosis['source_events']} source updates "
            "arrived by the simulation horizon."
        )
        if first.quote is None:
            st.warning("No quote was available when the order arrived.")
        elif first.quote_age_ms > scenario.policy.freshness_ms:
            st.warning(
                f"The arrival quote is older than the {scenario.policy.freshness_ms} ms "
                "freshness limit. Immediate submission accepts stale information."
            )
        else:
            st.success("The arrival quote is within the configured age limit.")
        if scenario.faults.latency_ms > scenario.policy.freshness_ms:
            st.info(
                "Fixed latency exceeds the age limit: fresh-data execution is unattainable "
                "unless a timeout fallback is enabled. This confirms a rule, not an edge."
            )
    with right:
        st.markdown("#### 02 · Policy responses & trade-offs")
        for result in results:
            actions = list(dict.fromkeys(t.decision.action.value.title() for t in result.trace))
            outcome = (
                f"filled after {result.execution_delay_ms} ms; "
                f"shortfall ${result.fill.implementation_shortfall:.4f}"
                if result.fill
                else f"unfilled · {result.reason}"
            )
            st.write(f"**{result.policy}** · {' → '.join(actions)} · {outcome}")
        st.caption(
            "Waiting can improve or worsen cost. Pausing avoids submission but creates "
            "non-execution and possible opportunity cost; it is not a zero-cost fill."
        )
    rows = []
    for result in results:
        rows.append(
            dict(
                policy=result.policy,
                scenario=scenario.name,
                seed=scenario.market.seed,
                filled=result.fill is not None,
                implementation_shortfall=result.fill.implementation_shortfall
                if result.fill
                else None,
                **exposure_metrics(result, scenario.policy.freshness_ms),
            )
        )
    for message in comparison_insights(pd.DataFrame(rows)):
        if "lower filled cost" in message or "identical" in message:
            st.write(message)
    st.markdown("#### 03 · Confidence & next question")
    st.info(
        "One seeded path explains mechanics, not expected performance. Run matched repeated "
        "trials to inspect completion, paired costs, uncertainty and penalty sensitivity. "
        "Synthetic GBM and fixed liquidity are uncalibrated; there is no universal best policy."
    )
    st.button(
        "Compare across seeds",
        on_click=lambda: st.session_state.update(workspace="Policy Comparison"),
        type="primary",
    )
    with st.expander("Scenario assumptions and exact configuration"):
        st.write(
            f"Buy {scenario.order.quantity:g} shares; arrival {scenario.order.arrival_ms} ms; "
            f"deadline {scenario.order.deadline_ms} ms; "
            f"maximum wait {scenario.policy.max_wait_ms} ms. "
            f"Missing-update probability {scenario.faults.missing_probability:.0%}. "
            "All-or-none execution uses truth at execution time, never an old observed price."
        )
        st.json(asdict(scenario), expanded=False)


def market_view(scenario: Scenario, events, deliveries, results) -> None:
    st.caption("RETROSPECTIVE EVALUATION · truth and fault labels are hidden from policies.")
    chart(price_figure(events, deliveries, results, scenario), "market-prices")
    st.caption(
        "Solid teal: simulated truth. Dashed blue: last delivered quote. Action markers "
        "use the observed price, never the hidden true price. No-quote actions appear below."
    )
    chart(decision_timeline(results), "market-decisions")
    reliability = reliability_frame(events, deliveries, scenario.policy.freshness_ms)
    a, b = st.columns(2)
    with a:
        age = px.line(
            reliability,
            x="time_ms",
            y="quote_age_ms",
            title="Quote age versus the freshness limit (ms)",
            labels={"time_ms": "Simulation time (ms)", "quote_age_ms": "Quote age (ms)"},
            color_discrete_sequence=COLORS,
        )
        age.add_hline(
            y=scenario.policy.freshness_ms,
            line_dash="dash",
            line_color="#fbbf24",
            annotation_text="Freshness limit",
        )
        chart(age, "quote-age")
    with b:
        chart(
            px.scatter(
                reliability,
                x="time_ms",
                y="state",
                color="state",
                title="Information reliability at each market tick",
                color_discrete_map={
                    "Within age threshold": "#2dd4bf",
                    "Stale": "#fbbf24",
                    "Unavailable": "#fb7185",
                },
                hover_data=["quote_age_ms"],
            ),
            "reliability-state",
        )
    st.write(
        "A flat observed price may mean a held quote, not a quiet market. The age limit "
        "measures information freshness; it cannot tell a policy the hidden price error."
    )
    delivered_ids = {d.quote.event_id for d in deliveries}
    timeline = pd.DataFrame(
        [
            dict(
                event_time_ms=e.event_time_ms,
                delivery_time_ms=e.event_time_ms + scenario.faults.latency_ms,
                status="Delivered" if e.event_id in delivered_ids else "Suppressed",
            )
            for e in events
        ]
    )
    with st.expander("Source-to-delivery diagnostics and exports"):
        chart(
            px.scatter(
                timeline,
                x="event_time_ms",
                y="delivery_time_ms",
                color="status",
                title="Actual deliveries and retrospectively suppressed updates",
                color_discrete_map={"Delivered": COLORS[0], "Suppressed": "#fb7185"},
            ),
            "timeline",
        )
        st.caption(
            "Suppression may have overlapping causes. Deliveries beyond the horizon are "
            "retained in this export, but not used by evaluation after the horizon."
        )
        st.download_button(
            "Download market path CSV",
            pd.DataFrame([asdict(e) for e in events]).to_csv(index=False),
            "market_path.csv",
            "text/csv",
        )
        st.download_button(
            "Download delivered quotes CSV",
            pd.DataFrame([asdict(d.quote) for d in deliveries]).to_csv(index=False),
            "delivered_quotes.csv",
            "text/csv",
        )


def result_view(result, prefix: str) -> None:
    st.success(f"CURRENT RESULTS · {result.records.seed.nunique()} executed seeds per scenario")
    st.caption(
        "Matched market paths, orders and delivered information. Costs and delay below "
        "are conditional on fills; completion is reported separately."
    )
    messages = comparison_insights(result.records)
    st.write(next(m for m in messages if m.startswith("Completion —")))
    if result.records.seed.nunique() < 30:
        st.caption("PREVIEW EVIDENCE · few seeds; inspect intervals and repeat with more trials.")
    with st.expander("Evidence-based interpretation and trade-offs"):
        for message in messages:
            st.write(message)
    outcomes, quality, penalties, details = st.tabs(
        ["Execution outcomes", "Data-quality exposure", "Penalty sensitivity", "Records & export"]
    )
    with outcomes:
        a, b = st.columns(2)
        summary = result.summary.copy()
        summary["fill_upper"] = summary.completion_ci_high - summary.completion_rate
        summary["fill_lower"] = summary.completion_rate - summary.completion_ci_low
        summary["cost_upper"] = summary.mean_shortfall_ci_high - summary.mean_shortfall
        summary["cost_lower"] = summary.mean_shortfall - summary.mean_shortfall_ci_low
        with a:
            chart(
                px.bar(
                    summary,
                    x="policy",
                    y="completion_rate",
                    color="scenario",
                    error_y="fill_upper",
                    error_y_minus="fill_lower",
                    barmode="group",
                    range_y=[0, 1.05],
                    title="Completion · 95% Wilson interval",
                ),
                prefix + "completion",
            )
        with b:
            chart(
                px.bar(
                    summary,
                    x="policy",
                    y="mean_shortfall",
                    color="scenario",
                    error_y="cost_upper",
                    error_y_minus="cost_lower",
                    barmode="group",
                    title="Filled shortfall ($) · 95% mean interval",
                ),
                prefix + "cost",
            )
        st.caption(
            "Mean intervals need at least two fills. Comparisons can use different filled "
            "subsets; intervals are unadjusted for multiple testing."
        )
        a, b = st.columns(2)
        with a:
            chart(
                px.bar(
                    summary,
                    x="policy",
                    y="average_delay_ms",
                    color="scenario",
                    barmode="group",
                    title="Filled execution delay (ms)",
                ),
                prefix + "delay",
            )
        with b:
            chart(
                px.bar(
                    summary,
                    x="policy",
                    y="non_execution_rate",
                    color="scenario",
                    barmode="group",
                    range_y=[0, 1],
                    title="Non-execution rate",
                ),
                prefix + "unfilled",
            )
        filled = result.records[result.records.filled]
        if len(filled):
            a, b = st.columns(2)
            with a:
                chart(
                    px.box(
                        filled,
                        x="policy",
                        y="implementation_shortfall",
                        color="scenario",
                        points="all",
                        title="Filled cost distribution ($)",
                    ),
                    prefix + "box",
                )
            with b:
                chart(
                    px.bar(
                        summary,
                        x="policy",
                        y="p95_shortfall",
                        color="scenario",
                        barmode="group",
                        title="95th percentile filled cost ($)",
                    ),
                    prefix + "tail",
                )
        else:
            st.info("No orders filled. Cost distributions are undefined, not zero.")
        st.dataframe(comparison_table(result.summary).round(4), hide_index=True, width="stretch")
        st.markdown("#### What did waiting cost on the same paths?")
        st.dataframe(joint_fill_comparisons(result.records), hide_index=True, width="stretch")
        st.caption(
            "Policy minus Always Execute on jointly filled seeds only. Positive means "
            "more expensive; negative means cheaper. This selected subset excludes "
            "missed orders, so consult completion and penalties too."
        )
    with quality:
        a, b = st.columns(2)
        with a:
            chart(
                px.bar(
                    summary,
                    x="policy",
                    y="stale_fill_rate",
                    color="scenario",
                    barmode="group",
                    range_y=[0, 1],
                    title="Stale observation at execution · fraction of fills",
                ),
                prefix + "stale",
            )
        with b:
            chart(
                px.bar(
                    summary,
                    x="policy",
                    y="pending_stale_fraction",
                    color="scenario",
                    barmode="group",
                    range_y=[0, 1],
                    title="Time-weighted stale exposure while pending",
                ),
                prefix + "exposure",
            )
        st.write(
            "Exposure uses delivered quote age, not a hidden price error. Pending exposure "
            "integrates time between decisions; immediate orders have no pending interval "
            "and therefore an undefined pending fraction. No-quote fills are tracked separately."
        )
        st.dataframe(
            summary[
                [
                    "scenario",
                    "policy",
                    "stale_fill_rate",
                    "no_quote_fill_rate",
                    "mean_execution_quote_age_ms",
                    "pending_stale_ms",
                    "pending_unavailable_ms",
                ]
            ],
            hide_index=True,
            width="stretch",
        )
    with penalties:
        st.write(
            "Unfilled score = positive endpoint price move × quantity + penalty/share × "
            "quantity. This is an illustrative counterfactual, not realized trading loss."
        )
        chart(
            px.line(
                result.sensitivity,
                x="penalty_per_share",
                y="mean_cost",
                color="policy",
                line_dash="scenario",
                markers=True,
                title="How the non-execution penalty changes adjusted costs",
            ),
            prefix + "sensitivity",
        )
        st.dataframe(result.paired, hide_index=True, width="stretch")
        st.caption(
            "Paired differences are policy minus Always Execute. Do not choose a winner "
            "from a single penalty value or conditional filled cost."
        )
    with details:
        st.dataframe(result.records, hide_index=True, width="stretch")
        with st.expander("Exact configuration and seeds"):
            st.json(reproducibility_manifest(result.manifest), expanded=False)
        for name in ("records", "summary", "paired", "sensitivity"):
            st.download_button(
                f"Download {name} CSV",
                getattr(result, name).to_csv(index=False),
                f"{name}.csv",
                "text/csv",
                key=prefix + "download-" + name,
            )
        st.download_button(
            "Download joint-fill comparison CSV",
            joint_fill_comparisons(result.records).to_csv(index=False),
            "joint_fills.csv",
            "text/csv",
            key=prefix + "joint-export",
        )
        st.download_button(
            "Download reproducibility manifest",
            json.dumps(reproducibility_manifest(result.manifest), indent=2),
            "manifest.json",
            "application/json",
            key=prefix + "manifest",
        )


def run_panel(
    scenarios: tuple[Scenario, ...],
    trials: int,
    penalty: float,
    key: str,
    policy_names: tuple[str, ...] | None = None,
    context: Scenario | None = None,
):
    if policy_names == ():
        st.info("Select at least one policy to run.")
        return None
    fingerprint = repr((scenarios, trials, penalty, policy_names))
    if st.button("Run matched experiment", type="primary", key=key + "run"):
        with st.spinner(f"Executing {trials} seeds per scenario…"):
            result = experiment(
                scenarios,
                tuple(range(scenarios[0].market.seed, scenarios[0].market.seed + trials)),
                penalty,
                policy_names,
            )
        st.session_state[key] = (fingerprint, result)
        st.session_state["latest_evidence"] = result
        st.session_state["latest_evidence_context"] = repr(
            (context or scenarios[0], trials, penalty)
        )
    saved = st.session_state.get(key)
    if saved and saved[0] == fingerprint:
        result_view(saved[1], key)
        return saved[1]
    if saved:
        st.warning("Configuration changed. Run again to display matching results.")
    else:
        st.info("Run the experiment to produce results. No precomputed findings are displayed.")
    return None


def decision_view(scenario: Scenario, events, deliveries, results) -> None:
    selected = st.selectbox("Policy to inspect", [r.policy for r in results])
    result = next(r for r in results if r.policy == selected)
    chart(decision_timeline((result,)), "explorer-actions")
    index = st.select_slider("Decision event", options=list(range(len(result.trace))), value=0)
    item = result.trace[index]
    obs = item.observation
    a, b, c = st.columns(3)
    a.metric("Decision time (ms)", obs.time_ms)
    b.metric("Quote age (ms)", obs.quote_age_ms if obs.quote else "Unavailable")
    c.metric("Action", item.decision.action.value.title())
    st.info(item.decision.reason)
    st.markdown("#### Information available at decision time")
    if obs.quote:
        quote = obs.quote
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Observed mid ($)": quote.mid,
                        "Source time (ms)": quote.event_time_ms,
                        "Delivered at (ms)": quote.delivery_time_ms,
                        "Quote age (ms)": obs.quote_age_ms,
                        "Spread ($)": quote.spread,
                        "Ask liquidity (shares)": quote.ask_liquidity,
                        "Last observed sequence gap": obs.last_sequence_gap,
                    }
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.warning("No delivered quote was available. This is not a zero price or zero risk.")
    st.write(
        f"Freshness limit {scenario.policy.freshness_ms} ms · maximum wait "
        f"{scenario.policy.max_wait_ms} ms · elapsed {obs.time_ms - scenario.order.arrival_ms} ms."
    )
    fig = price_figure(events, deliveries, (result,), scenario)
    fig.add_vline(
        x=obs.time_ms, line_dash="dash", line_color="#e6edf5", annotation_text="Selected decision"
    )
    chart(fig, "explorer-market")
    st.caption(
        "The chart's true prices and later decisions are retrospective context, "
        "not information available at the selected decision time."
    )
    st.markdown("#### Retrospective outcome — hidden from policy")
    st.write("Final outcome:", "Filled" if result.fill else "Unfilled", "·", result.reason)
    if result.fill:
        fill = result.fill
        a, b, c = st.columns(3)
        a.metric("Actual execution time", f"{fill.time_ms} ms")
        b.metric("Actual execution price", f"${fill.execution_price:.5f}")
        c.metric("Implementation shortfall", f"${fill.implementation_shortfall:.4f}")
        st.caption(
            "Execution uses the venue truth at actual submission; historical observed "
            "quotes are not executable prices. Shortfall includes fees exactly once."
        )
    else:
        st.write(
            f"Illustrative endpoint opportunity cost: ${result.opportunity_cost:.4f}. "
            "No execution cost or filled-order delay is assigned."
        )
    rows = decision_frame((result,))
    st.dataframe(rows, hide_index=True, width="stretch")
    with st.expander("Raw observation and exact outcome"):
        st.json(asdict(obs), expanded=False)
        st.json(
            asdict(result.fill) if result.fill else {"unfilled_reason": result.reason},
            expanded=False,
        )
    st.download_button(
        "Download decision trace CSV", rows.to_csv(index=False), "decision_trace.csv", "text/csv"
    )


def insights_view(scenario: Scenario, trials: int, penalty: float) -> None:
    result = st.session_state.get("latest_evidence")
    if result is None:
        st.info("Evidence is insufficient. Run a policy comparison or stress experiment first.")
        return
    if st.session_state.get("latest_evidence_context") != repr((scenario, trials, penalty)):
        st.warning(
            "OUTDATED RESULTS · controls differ from the last executed experiment. "
            "The findings below describe its saved configuration, not the current controls."
        )
    else:
        st.success("CURRENT EVIDENCE · last executed experiment matches the current controls")
    for message in comparison_insights(result.records):
        st.write(message)
    st.markdown("#### Operational questions informed by this run")
    st.write(
        "Does waiting change fill probability enough to justify its additional price exposure? "
        "Would a stricter age rule simply prevent execution? Does a conclusion survive "
        "different penalties and seeds? The prototype exposes these questions; it does "
        "not approve a production trading policy."
    )
    st.dataframe(comparison_table(result.summary), hide_index=True, width="stretch")
    st.dataframe(joint_fill_comparisons(result.records), hide_index=True, width="stretch")
    chart(
        px.line(
            result.sensitivity,
            x="penalty_per_share",
            y="mean_cost",
            color="policy",
            line_dash="scenario",
            markers=True,
            title="Penalty assumptions change the trade-off",
        ),
        "insight-penalties",
    )
    st.warning(
        "Synthetic evidence only. Joint fills can be a selected subset; unadjusted "
        "intervals and preview tail estimates need caution. No empirical calibration "
        "or real-world optimality is established."
    )
    with st.expander("Evidence configuration and paired adjusted costs"):
        st.dataframe(result.paired, hide_index=True)
        st.json(reproducibility_manifest(result.manifest), expanded=False)


def render() -> None:
    st.set_page_config(
        page_title="MarketLens · Trading Under Uncertainty",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """<style>
        .block-container {padding-top: 2.5rem; padding-bottom: 2rem; max-width: 1650px;}
        [data-testid="stMetric"] {background: #142139; border: 1px solid #23354f;
            border-top: 2px solid #27b7aa; border-radius: 8px; padding: 14px 16px;}
        [data-testid="stMetricLabel"] {color: #b8c8dc;}
        h3 {letter-spacing: -0.015em;}
        </style>""",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("## MarketLens\nTrading Under Uncertainty")
    page = st.sidebar.radio("Research workspace", PAGES, key="workspace")
    st.title("MarketLens")
    st.caption(
        "Making better trading execution decisions when market information is delayed, "
        "incomplete, or unreliable."
    )
    st.subheader(page)
    try:
        scenario, trials, penalty = controls()
        events, deliveries, results = sample(scenario)
        if page == PAGES[0]:
            overview(scenario, events, deliveries, results)
        elif page == PAGES[1]:
            market_view(scenario, events, deliveries, results)
        elif page == PAGES[2]:
            st.write(
                "Matched paths, orders, delivered information "
                "and arrival benchmarks across policies."
            )
            names = [p.name for p in standard_policies()]
            chosen = st.multiselect("Policies to compare", names, default=names)
            result = run_panel((scenario,), trials, penalty, "comparison", tuple(chosen))
            if result is not None and chosen:
                st.markdown("#### Selected policy summary")
                st.dataframe(result.summary[result.summary.policy.isin(chosen)], hide_index=True)
        elif page == PAGES[3]:
            suite = st.selectbox(
                "Stress suite",
                [
                    "tradeoffs",
                    "waiting",
                    "urgency",
                    "volatility_latency",
                    "latency",
                    "missing",
                    "volatility",
                    "liquidity",
                    "combined",
                    "thresholds",
                    "heatmap",
                ],
            )
            st.caption(
                "Volatility is annualised. Liquidity suite applies the low-liquidity preset "
                "(0.1x displayed size, 3x spread). Heatmap uses conditional filled costs."
            )
            st.info(
                "Rule checks (for example, latency above the age limit) explain mechanical "
                "non-execution. Intermittent-feed, waiting and urgency sweeps measure price "
                "exposure and missed execution on matched paths; inspect both favorable "
                "and unfavorable paired outcomes."
            )
            scenarios = scenario_suite(suite, scenario)
            result = run_panel(scenarios, trials, penalty, "stress", context=scenario)
            if result is not None and suite in {"heatmap", "volatility_latency"}:
                policy = st.selectbox("Heatmap policy", list(result.summary.policy.unique()))
                table = result.summary[result.summary.policy == policy].copy()
                lookup = {s.name: (s.market.volatility, s.faults.latency_ms) for s in scenarios}
                table["volatility"] = table.scenario.map(lambda n: lookup[n][0])
                table["latency_ms"] = table.scenario.map(lambda n: lookup[n][1])
                grid = table.pivot(
                    index="volatility", columns="latency_ms", values="mean_shortfall"
                )
                chart(
                    go.Figure(
                        go.Heatmap(
                            x=grid.columns,
                            y=grid.index,
                            z=grid.values,
                            colorbar_title="Shortfall ($)",
                        )
                    ).update_layout(
                        xaxis_title="Latency (ms)", yaxis_title="Annualised volatility"
                    ),
                    "heatmap",
                )
                st.caption("Empty cells mean no fills; consult completion in the summary.")
        elif page == PAGES[4]:
            decision_view(scenario, events, deliveries, results)
        elif page == PAGES[5]:
            insights_view(scenario, trials, penalty)
        else:
            root = Path(__file__).resolve().parents[2] / "docs"
            for filename in ("methodology.md", "limitations.md"):
                st.markdown((root / filename).read_text())
    except ValueError as error:
        st.error(f"Invalid scenario: {error}")
