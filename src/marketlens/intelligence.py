"""Retrospective diagnostics and explanations, never inputs to decision policies."""

from collections.abc import Sequence

import numpy as np
import pandas as pd

from marketlens.events import Delivery, MarketEvent
from marketlens.execution import Evaluation
from marketlens.observations import ObservationCursor


def exposure_metrics(outcome: Evaluation, freshness_ms: int) -> dict:
    """Integrate held-quote state between decisions; don't average irregular ticks."""
    stale_ms = unavailable_ms = 0
    for left, right in zip(outcome.trace, outcome.trace[1:], strict=False):
        start, end = left.observation.time_ms, right.observation.time_ms
        quote = left.observation.quote
        if quote is None:
            unavailable_ms += end - start
        else:
            stale_ms += max(0, end - max(start, quote.event_time_ms + freshness_ms))
    last = outcome.trace[-1].observation
    duration = last.time_ms - outcome.trace[0].observation.time_ms
    return dict(
        execution_quote_age_ms=last.quote_age_ms if outcome.fill else None,
        executed_on_stale_quote=bool(
            outcome.fill and last.quote_age_ms is not None and last.quote_age_ms > freshness_ms
        ),
        executed_without_quote=bool(outcome.fill and last.quote is None),
        pending_duration_ms=duration,
        pending_stale_ms=stale_ms,
        pending_unavailable_ms=unavailable_ms,
        pending_stale_fraction=stale_ms / duration if duration else None,
    )


def reliability_frame(
    events: Sequence[MarketEvent], deliveries: Sequence[Delivery], freshness_ms: int
) -> pd.DataFrame:
    cursor = ObservationCursor(deliveries)
    observations = [cursor.at(e.event_time_ms) for e in events]
    return pd.DataFrame(
        [
            dict(
                time_ms=o.time_ms,
                observed_mid=o.quote.mid if o.quote else None,
                quote_age_ms=o.quote_age_ms,
                state=(
                    "Unavailable"
                    if o.quote is None
                    else "Stale"
                    if o.quote_age_ms > freshness_ms
                    else "Within age threshold"
                ),
            )
            for o in observations
        ]
    )


def scenario_diagnosis(
    events: Sequence[MarketEvent], deliveries: Sequence[Delivery], freshness_ms: int
) -> dict:
    """Truth/suppression counts are explicitly retrospective, not live fault detection."""
    horizon = events[-1].event_time_ms
    in_horizon = [d for d in deliveries if d.delivery_time_ms <= horizon]
    frame = reliability_frame(events, deliveries, freshness_ms)
    return dict(
        source_events=len(events),
        suppressed_updates=len(events) - len(deliveries),
        in_flight_after_horizon=len(deliveries) - len(in_horizon),
        delivered_by_horizon=len(in_horizon),
        stale_grid_fraction=float((frame.state == "Stale").mean()),
        unavailable_grid_fraction=float((frame.state == "Unavailable").mean()),
        max_quote_age_ms=(
            float(frame.quote_age_ms.max()) if frame.quote_age_ms.notna().any() else None
        ),
        realized_mid_range=float(max(e.mid for e in events) - min(e.mid for e in events)),
    )


def comparison_insights(records: pd.DataFrame) -> list[str]:
    """Explain executed outcomes, including ties, without choosing a universal winner."""
    messages = []
    for name, group in records.groupby("scenario", sort=False):
        n = group.seed.nunique()
        messages.append(f"{name}: {n} executed seeds; compare completion before conditional cost.")
        filled_rates = group.groupby("policy", sort=False).filled.mean()
        messages.append(
            "Completion — " + "; ".join(f"{p}: {v:.0%}" for p, v in filled_rates.items()) + "."
        )
        if not group.filled.any():
            messages.append(
                "No orders filled. Execution costs are undefined, not zero-cost success."
            )
            continue
        filled = group[group.filled]
        costs = filled.groupby("policy").implementation_shortfall.mean()
        if (
            len(filled_rates) > 1
            and filled_rates.nunique() == 1
            and len(costs) == len(filled_rates)
            and np.allclose(costs.to_numpy(), costs.iloc[0], rtol=0, atol=1e-9)
        ):
            messages.append(
                "Mean filled costs and completion are identical across tested policies. "
                "Acceptable data or common terminal actions can make the rules coincide; "
                "this is a valid result, not a reason to hide the baseline."
            )
        baseline = group[group.policy == "Always Execute"].set_index("seed")
        if baseline.empty:
            messages.append(
                "Always Execute was not selected; baseline comparisons are unavailable."
            )
        for policy in group.policy.unique():
            if policy == "Always Execute" or baseline.empty:
                continue
            other = group[group.policy == policy].set_index("seed")
            pairs = other.merge(
                baseline,
                left_index=True,
                right_index=True,
                suffixes=("_policy", "_base"),
                how="left",
            )
            joint = pairs[pairs.filled_policy & pairs.filled_base]
            if len(joint):
                delta = joint.implementation_shortfall_policy - joint.implementation_shortfall_base
                lower = int((delta < -1e-9).sum())
                higher = int((delta > 1e-9).sum())
                messages.append(
                    f"{policy}: lower filled cost in {lower}/{len(joint)} jointly filled "
                    f"seeds, higher in {higher}/{len(joint)}; mean difference "
                    f"${delta.mean():+.4f} per order. Joint fills can be a selected subset."
                )
        stale = int(filled.executed_on_stale_quote.sum())
        missing = int(filled.executed_without_quote.sum())
        messages.append(
            f"{stale}/{len(filled)} fills used an observation older than its configured "
            f"age threshold; {missing}/{len(filled)} had no quote. These describe "
            "submission information, not an executable historical price."
        )
        if n < 30:
            messages.append(
                "Preview evidence: few seeds; tail estimates and intervals are unstable."
            )
    messages.append(
        "No universal winner: include non-execution, waiting, penalty sensitivity and "
        "model uncertainty. Policies never use retrospective truth to choose actions."
    )
    return messages
