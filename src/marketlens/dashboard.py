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
from marketlens.experiments import Scenario, fault_seed, run_experiment, scenario_suite
from marketlens.faults import inject_faults
from marketlens.market import simulate_market
from marketlens.observations import ObservationCursor
from marketlens.policies import standard_policies
from marketlens.reporting import reproducibility_manifest

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
    st.plotly_chart(fig, width="stretch", key=key)


def controls() -> tuple[Scenario, int, float]:
    with st.sidebar:
        st.markdown("### Scenario configuration")
        regime = st.selectbox("Market regime", list(Regime), format_func=lambda x: x.value)
        seed = st.number_input("Random seed", min_value=0, max_value=1_000_000, value=42, step=1)
        with st.expander("Market", expanded=False):
            price = st.number_input("Initial price ($/share)", min_value=1.0, value=100.0)
            volatility = st.slider("Annualised volatility", 0.0, 3.0, 0.2, 0.05)
            drift = st.number_input("Annualised drift", value=0.0, step=0.01)
            liquidity = st.number_input("Base liquidity (shares/side)", 0.0, 100000.0, 1000.0)
            spread = st.number_input("Base spread ($/share)", 0.0, 1.0, 0.02, 0.01)
            seconds = st.slider("Simulation duration (seconds)", 2, 60, 10)
            step = st.selectbox("Market time step (ms)", [10, 50, 100], index=1)
        horizon = seconds * 1000
        with st.expander("Data reliability", expanded=False):
            latency = st.select_slider("Data latency (ms)", [0, 50, 100, 250, 500, 1000], value=0)
            missing = st.slider("Missing-update probability", 0.0, 1.0, 0.0, 0.05)
            outage_start = st.number_input("Outage start (ms)", 0, horizon, min(900, horizon))
            outage_length = st.number_input("Outage duration (ms)", 0, horizon, 0, step=50)
            stale_start = st.number_input("Stale window start (ms)", 0, horizon, min(900, horizon))
            stale_length = st.number_input("Stale window duration (ms)", 0, horizon, 0, step=50)
        with st.expander("Order and policy thresholds", expanded=False):
            arrival = st.slider("Order arrival (ms)", 0, horizon, min(1000, horizon), step=50)
            deadline = st.slider(
                "Execution deadline (ms)",
                arrival,
                horizon,
                min(max(5000, arrival), horizon),
                step=50,
            )
            quantity = st.number_input("Order quantity (shares)", 1.0, 100000.0, 100.0)
            fee = st.number_input("Fee ($/share)", 0.0, 1.0, 0.001, step=0.001, format="%.3f")
            impact = st.number_input("Impact coefficient ($/share)", 0.0, 10.0, 0.01)
            reference = st.number_input("Benchmark price (0 = arrival mid)", 0.0, 100000.0, 0.0)
            freshness = st.number_input("Freshness threshold (ms)", 0, 10000, 100, step=50)
            wait = st.number_input("Maximum wait (ms)", 0, 10000, 500, step=50)
            silence = st.number_input("Pause after delivery silence (ms)", 0, 10000, 1000, step=50)
            max_spread = st.number_input("Maximum observed spread ($/share)", 0.0, 10.0, 0.1)
            max_gap = st.number_input("Maximum last observed sequence gap", 0, 10000, 5)
            timeout = st.checkbox("Wait policy executes at timeout", value=False)
        with st.expander("Repeated experiments", expanded=False):
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
        Scenario("Configured scenario", market, faults, order, policy, step),
        (10 if preview else trials),
        penalty,
    )


def market_view(scenario: Scenario, events, deliveries) -> None:
    st.caption("Ground truth is a retrospective evaluation view, unavailable to policies.")
    cursor = ObservationCursor(deliveries)
    observations = [cursor.at(e.event_time_ms) for e in events]
    frame = pd.DataFrame(
        {
            "time_ms": [e.event_time_ms for e in events],
            "Ground truth (retrospective)": [e.mid for e in events],
            "Observed quote": [o.quote.mid if o.quote else None for o in observations],
        }
    )
    fig = px.line(
        frame,
        x="time_ms",
        y=["Ground truth (retrospective)", "Observed quote"],
        labels={"time_ms": "Simulation time (ms)", "value": "Price ($/share)"},
        color_discrete_sequence=COLORS,
    )
    for interval in scenario.faults.outage_intervals:
        fig.add_vrect(
            x0=interval.start_ms,
            x1=interval.end_ms,
            opacity=0.15,
            fillcolor="red",
            line_width=0,
            annotation_text="Delivery outage",
        )
    for interval in scenario.faults.stale_intervals:
        fig.add_vrect(
            x0=interval.start_ms,
            x1=interval.end_ms,
            opacity=0.15,
            fillcolor="orange",
            line_width=0,
            annotation_text="Source stale window",
        )
    chart(fig, "market-prices")
    age = pd.DataFrame(
        {
            "time_ms": [o.time_ms for o in observations],
            "quote_age_ms": [o.quote_age_ms for o in observations],
        }
    )
    chart(
        px.line(
            age,
            x="time_ms",
            y="quote_age_ms",
            title="Age of last delivered quote (ms)",
            color_discrete_sequence=COLORS,
        ),
        "quote-age",
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
    chart(
        px.scatter(
            timeline,
            x="event_time_ms",
            y="delivery_time_ms",
            color="status",
            title="Delivery timeline and suppressed-update markers",
            color_discrete_map={"Delivered": COLORS[0], "Suppressed": "#fb7185"},
        ),
        "timeline",
    )
    st.caption(
        "Suppression markers are retrospective diagnostics, not policy-visible fault labels. "
        "Deliveries beyond the source horizon are shown here but not evaluated."
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
    st.caption(
        f"Executed {result.records.seed.nunique()} seeds per scenario. "
        "Shortfall and delay summaries are conditional on fills; completion is separate."
    )
    a, b = st.columns(2)
    with a:
        chart(
            px.bar(
                result.summary,
                x="policy",
                y="mean_shortfall",
                color="scenario",
                barmode="group",
                title="Mean filled-order shortfall ($ total)",
            ),
            prefix + "cost",
        )
    with b:
        chart(
            px.bar(
                result.summary,
                x="policy",
                y="completion_rate",
                color="scenario",
                barmode="group",
                range_y=[0, 1],
                title="Completion rate",
            ),
            prefix + "completion",
        )
    chart(
        px.bar(
            result.summary,
            x="policy",
            y="average_delay_ms",
            color="scenario",
            barmode="group",
            title="Average filled-order execution delay (ms)",
        ),
        prefix + "delay",
    )
    filled = result.records[result.records.filled]
    if len(filled):
        chart(
            px.box(
                filled,
                x="policy",
                y="implementation_shortfall",
                color="scenario",
                title="Filled-order cost distribution ($ total)",
                points="all",
            ),
            prefix + "box",
        )
        chart(
            px.bar(
                result.summary,
                x="policy",
                y="p95_shortfall",
                color="scenario",
                barmode="group",
                title="95th percentile filled-order shortfall ($)",
            ),
            prefix + "tail",
        )
    else:
        st.info("No orders filled. Cost distributions are undefined, not zero.")
    st.dataframe(result.summary, hide_index=True, width="stretch")
    with st.expander("Paired penalty-adjusted comparisons and sensitivity"):
        st.markdown(
            "Differences are policy minus Always Execute. These scores depend on the "
            "non-execution counterfactual and penalty; they are not realized returns."
        )
        st.dataframe(result.paired, hide_index=True, width="stretch")
        chart(
            px.line(
                result.sensitivity,
                x="penalty_per_share",
                y="mean_cost",
                color="policy",
                line_dash="scenario",
                markers=True,
                title="Sensitivity to assumed non-execution penalty",
            ),
            prefix + "sensitivity",
        )
    with st.expander("Per-trial results and exact configuration"):
        st.dataframe(result.records, hide_index=True, width="stretch")
        st.json(result.manifest)
    for name in ("records", "summary", "paired", "sensitivity"):
        st.download_button(
            f"Download {name} CSV",
            getattr(result, name).to_csv(index=False),
            f"{name}.csv",
            "text/csv",
            key=prefix + "download-" + name,
        )
    st.download_button(
        "Download reproducibility manifest",
        json.dumps(reproducibility_manifest(result.manifest), indent=2),
        "manifest.json",
        "application/json",
        key=prefix + "manifest",
    )
    st.info(
        "Lower conditional cost alone does not establish a better policy: examine completion, "
        "tail costs, waiting time, paired uncertainty and penalty sensitivity together."
    )


def run_panel(
    scenarios: tuple[Scenario, ...],
    trials: int,
    penalty: float,
    key: str,
    policy_names: tuple[str, ...] | None = None,
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
    saved = st.session_state.get(key)
    if saved and saved[0] == fingerprint:
        result_view(saved[1], key)
        return saved[1]
    if saved:
        st.warning("Configuration changed. Run again to display matching results.")
    else:
        st.info("Run the experiment to produce results. No precomputed findings are displayed.")
    return None


def decision_view(results) -> None:
    selected = st.selectbox("Policy to inspect", [r.policy for r in results])
    result = next(r for r in results if r.policy == selected)
    trace = result.trace
    index = st.select_slider("Decision event", options=list(range(len(trace))), value=0)
    item = trace[index]
    obs = item.observation
    a, b, c = st.columns(3)
    a.metric("Decision time (ms)", obs.time_ms)
    b.metric("Quote age (ms)", obs.quote_age_ms if obs.quote else "Unavailable")
    c.metric("Action", item.decision.action.value)
    st.write(item.decision.reason)
    st.markdown("#### Information available at decision time")
    st.json(asdict(obs))
    st.markdown("#### Retrospective outcome — hidden from policy")
    st.write("Final outcome:", "Filled" if result.fill else "Unfilled", "·", result.reason)
    if result.fill:
        st.json(asdict(result.fill))
    else:
        st.write("Counterfactual opportunity cost ($ total):", result.opportunity_cost)
    rows = [
        dict(
            time_ms=t.observation.time_ms,
            quote_age_ms=t.observation.quote_age_ms,
            observed_event_id=t.observation.quote.event_id if t.observation.quote else None,
            action=t.decision.action.value,
            reason=t.decision.reason,
        )
        for t in trace
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.download_button(
        "Download decision trace CSV",
        pd.DataFrame(rows).to_csv(index=False),
        "decision_trace.csv",
        "text/csv",
    )


def insights_view() -> None:
    result = st.session_state.get("latest_evidence")
    if result is None:
        st.info("Evidence is insufficient. Run a policy comparison or stress experiment first.")
        return
    st.caption(
        "These statements describe the last executed experiment, whose configuration is below."
    )
    for name, group in result.summary.groupby("scenario", sort=False):
        st.markdown(f"#### {name}")
        max_completion = group.completion_rate.max()
        leaders = group[group.completion_rate == max_completion]
        st.write(
            f"Highest observed completion: {max_completion:.1%}, achieved by "
            + ", ".join(leaders.policy)
            + "."
        )
        filled = group.dropna(subset=["mean_shortfall"])
        if len(filled):
            best = filled.loc[filled.mean_shortfall.idxmin()]
            st.write(
                f"Lowest observed mean conditional shortfall: {best.policy} "
                f"(${best.mean_shortfall:.4f} total). This is not an overall policy ranking."
            )
        failed = group[group.completion_rate < 1]
        if len(failed):
            st.write("Incomplete execution occurred for: " + ", ".join(failed.policy) + ".")
        else:
            st.write("All tested policies completed in these trials.")
    st.warning(
        "Simulation evidence only. No real-market or commercial conclusion follows. "
        "Conditional cost comparisons may select different filled subsets. Confidence "
        "intervals are unadjusted for multiple comparisons; inspect paired differences."
    )
    st.write(
        "Product implications to investigate: communicate quote age, distinguish unavailable "
        "data from quiet prices, and show completion beside cost. Test thresholds across "
        "more seeds and assumptions before selecting a default policy."
    )
    st.dataframe(result.paired, hide_index=True, width="stretch")
    st.dataframe(result.sensitivity, hide_index=True, width="stretch")
    st.json(result.manifest)


def render() -> None:
    st.set_page_config(
        page_title="MarketLens · Trading Under Uncertainty",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.sidebar.markdown("## MarketLens\nTrading Under Uncertainty")
    page = st.sidebar.radio("Research workspace", PAGES)
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
            st.markdown("### How should execution adapt when market information is unreliable?")
            st.info(
                "Synthetic research platform. No live data, trading recommendations "
                "or brokerage connection."
            )
            a, b, c, d = st.columns(4)
            a.metric("Source market events", len(events))
            b.metric(
                "Delivered by horizon",
                sum(x.delivery_time_ms <= scenario.market.duration_ms for x in deliveries),
            )
            c.metric("Data latency", f"{scenario.faults.latency_ms} ms")
            d.metric(
                "Single-path completion", f"{sum(r.fill is not None for r in results)}/4 policies"
            )
            st.write(
                "Single seeded path, not repeated-trial evidence. Costs, waiting and completion "
                "can move in different directions; compare them together."
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        dict(
                            policy=r.policy,
                            filled=r.fill is not None,
                            shortfall=r.fill.implementation_shortfall if r.fill else None,
                            delay_ms=r.execution_delay_ms,
                            reason=r.reason,
                        )
                        for r in results
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
            with st.expander("Current configuration", expanded=True):
                st.json(asdict(scenario))
            st.write(
                "Assumptions: annualised GBM; fixed spread and displayed liquidity; marketable "
                "buys; all-or-none fills; fixed latency; independent update loss. "
                "Ground truth is used only for retrospective charts and execution evaluation."
            )
        elif page == PAGES[1]:
            market_view(scenario, events, deliveries)
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
            scenarios = scenario_suite(suite, scenario)
            result = run_panel(scenarios, trials, penalty, "stress")
            if result is not None and suite == "heatmap":
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
            decision_view(results)
        elif page == PAGES[5]:
            insights_view()
        else:
            root = Path(__file__).resolve().parents[2] / "docs"
            for filename in ("methodology.md", "limitations.md"):
                st.markdown((root / filename).read_text())
    except ValueError as error:
        st.error(f"Invalid scenario: {error}")
