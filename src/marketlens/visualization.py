"""Plotly views of executed simulations; all truth overlays are retrospective."""

from bisect import bisect_right
from collections.abc import Sequence

import pandas as pd
import plotly.graph_objects as go

from marketlens.events import Delivery, MarketEvent
from marketlens.execution import Evaluation
from marketlens.experiments import Scenario
from marketlens.observations import ObservationCursor

ACTION_STYLES = {
    "execute": ("#2dd4bf", "triangle-up"),
    "wait": ("#fbbf24", "diamond"),
    "pause": ("#fb7185", "x"),
}


def decision_frame(results: Sequence[Evaluation]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(
                policy=result.policy,
                time_ms=t.observation.time_ms,
                action=t.decision.action.value,
                reason=t.decision.reason,
                quote_age_ms=t.observation.quote_age_ms,
                observed_mid=t.observation.quote.mid if t.observation.quote else None,
                observed_event_id=t.observation.quote.event_id if t.observation.quote else None,
            )
            for result in results
            for t in result.trace
        ]
    )


def decision_timeline(results: Sequence[Evaluation]) -> go.Figure:
    frame = decision_frame(results)
    fig = go.Figure()
    for action, (color, symbol) in ACTION_STYLES.items():
        group = frame[frame.action == action]
        if group.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=group.time_ms,
                y=group.policy,
                mode="markers",
                name=action.title(),
                marker=dict(color=color, symbol=symbol, size=12),
                customdata=group[["reason", "quote_age_ms", "observed_event_id"]].to_numpy(),
                hovertemplate="%{y}<br>Decision %{x} ms<br>%{customdata[0]}"
                "<br>Quote age: %{customdata[1]} ms"
                "<br>Observed event: %{customdata[2]}<extra></extra>",
            )
        )
    fig.update_layout(
        title="How each policy responds · hover for the reason",
        xaxis_title="Decision time (ms)",
        yaxis_title=None,
        height=310,
    )
    return fig


def price_figure(
    events: Sequence[MarketEvent],
    deliveries: Sequence[Delivery],
    results: Sequence[Evaluation],
    scenario: Scenario,
) -> go.Figure:
    times = sorted(
        {e.event_time_ms for e in events}
        | {d.delivery_time_ms for d in deliveries if d.delivery_time_ms <= events[-1].event_time_ms}
    )
    source_times = [e.event_time_ms for e in events]
    cursor = ObservationCursor(deliveries)
    quotes = [cursor.at(t).quote for t in times]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=times,
            y=[events[bisect_right(source_times, t) - 1].mid for t in times],
            mode="lines",
            name="Ground truth · retrospective only",
            line=dict(color="#2dd4bf", width=2, shape="hv"),
            hovertemplate="%{x} ms<br>True mid $%{y:.5f} · hidden from policy<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=[q.mid if q else None for q in quotes],
            mode="lines",
            name="Last delivered quote · policy-visible",
            line=dict(color="#93c5fd", width=2, dash="dash", shape="hv"),
            connectgaps=False,
            customdata=[
                [q.event_time_ms, t - q.event_time_ms] if q else [None, None]
                for q, t in zip(quotes, times, strict=True)
            ],
            hovertemplate="%{x} ms<br>Observed mid $%{y:.5f}<br>Source %{customdata[0]} ms"
            "<br>Quote age %{customdata[1]} ms<extra></extra>",
        )
    )
    frame = decision_frame(results)
    for action, (color, symbol) in ACTION_STYLES.items():
        group = frame[(frame.action == action) & frame.observed_mid.notna()]
        if group.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=group.time_ms,
                y=group.observed_mid,
                mode="markers",
                name=action.title(),
                marker=dict(color=color, symbol=symbol, size=11),
                customdata=group[["policy", "reason", "quote_age_ms"]].to_numpy(),
                hovertemplate="%{customdata[0]} · " + action + "<br>%{customdata[1]}"
                "<br>At %{x} ms, observed $%{y:.5f}"
                "<br>Age %{customdata[2]} ms<extra></extra>",
            )
        )
    for interval in scenario.faults.outage_intervals:
        fig.add_vrect(
            x0=interval.start_ms,
            x1=interval.end_ms,
            opacity=0.1,
            fillcolor="#fb7185",
            line_width=0,
            annotation_text="Delivery outage",
        )
    for interval in scenario.faults.stale_intervals:
        fig.add_vrect(
            x0=interval.start_ms,
            x1=interval.end_ms,
            opacity=0.1,
            fillcolor="#fbbf24",
            line_width=0,
            annotation_text="Stale window",
        )
    fig.add_vline(
        x=scenario.order.arrival_ms,
        line_dash="dot",
        line_color="#94a3b8",
        annotation_text="Order arrival",
        annotation_position="bottom left",
    )
    fig.update_layout(
        title="Market truth versus the information actually delivered",
        xaxis_title="Simulation time (ms)",
        yaxis_title="Mid-price ($/share)",
        height=420,
    )
    return fig
