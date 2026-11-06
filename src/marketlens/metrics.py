"""Summaries from executed trials; filled costs and completion remain separate."""

import math

import numpy as np
import pandas as pd
from scipy import stats


def mean_interval(values: list[float] | np.ndarray) -> tuple[float | None, float | None]:
    """Two-sided 95% Student-t interval; undefined for fewer than two samples."""
    x = np.asarray(values, dtype=float)
    if len(x) < 2:
        return None, None
    mean = float(x.mean())
    se = float(x.std(ddof=1) / math.sqrt(len(x)))
    if se == 0:
        return mean, mean
    margin = float(stats.t.ppf(0.975, len(x) - 1) * se)
    return mean - margin, mean + margin


def wilson_interval(successes: int, n: int) -> tuple[float, float]:
    z = float(stats.norm.ppf(0.975))
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (
        0.0 if successes == 0 else max(0.0, center - margin),
        1.0 if successes == n else min(1.0, center + margin),
    )


def summarize(records: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (scenario, policy), group in records.groupby(["scenario", "policy"], sort=False):
        filled = group[group.filled]
        costs = filled.implementation_shortfall.to_numpy(dtype=float)
        n = len(group)
        low, high = mean_interval(costs)
        fill_low, fill_high = wilson_interval(len(filled), n)
        p95 = float(np.quantile(costs, 0.95)) if len(costs) else None
        rows.append(
            dict(
                scenario=scenario,
                policy=policy,
                trials=n,
                filled=len(filled),
                completion_rate=len(filled) / n,
                non_execution_rate=1 - len(filled) / n,
                completion_ci_low=fill_low,
                completion_ci_high=fill_high,
                mean_shortfall=float(costs.mean()) if len(costs) else None,
                median_shortfall=float(np.median(costs)) if len(costs) else None,
                std_shortfall=float(costs.std(ddof=1)) if len(costs) > 1 else None,
                p95_shortfall=p95,
                tail_mean_shortfall=float(costs[costs >= p95].mean()) if len(costs) else None,
                mean_shortfall_ci_low=low,
                mean_shortfall_ci_high=high,
                average_delay_ms=float(filled.execution_delay_ms.mean()) if len(filled) else None,
                mean_opportunity_cost_unfilled=(
                    float(group.loc[~group.filled, "opportunity_cost"].mean())
                    if len(filled) < n
                    else None
                ),
                mean_penalized_cost=float(group.penalized_cost.mean()),
                stale_fill_rate=(
                    float(filled.executed_on_stale_quote.mean()) if len(filled) else None
                ),
                no_quote_fill_rate=(
                    float(filled.executed_without_quote.mean()) if len(filled) else None
                ),
                mean_execution_quote_age_ms=(
                    float(filled.execution_quote_age_ms.mean())
                    if filled.execution_quote_age_ms.notna().any()
                    else None
                ),
                pending_stale_ms=float(group.pending_stale_ms.sum()),
                pending_unavailable_ms=float(group.pending_unavailable_ms.sum()),
                pending_stale_fraction=(
                    float(group.pending_stale_ms.sum() / group.pending_duration_ms.sum())
                    if group.pending_duration_ms.sum()
                    else None
                ),
            )
        )
    return pd.DataFrame(rows)


def paired_comparisons(records: pd.DataFrame, baseline: str = "Always Execute") -> pd.DataFrame:
    """Paired penalty-adjusted differences: policy minus baseline, lower is better."""
    rows = []
    for scenario, group in records.groupby("scenario", sort=False):
        pivot = group.pivot(index="seed", columns="policy", values="penalized_cost")
        if baseline not in pivot:
            continue
        for policy in pivot.columns:
            if policy == baseline:
                continue
            delta = (pivot[policy] - pivot[baseline]).dropna().to_numpy()
            low, high = mean_interval(delta)
            rows.append(
                dict(
                    scenario=scenario,
                    policy=policy,
                    baseline=baseline,
                    pairs=len(delta),
                    mean_cost_difference=float(delta.mean()),
                    ci_low=low,
                    ci_high=high,
                )
            )
    return pd.DataFrame(
        rows,
        columns=[
            "scenario",
            "policy",
            "baseline",
            "pairs",
            "mean_cost_difference",
            "ci_low",
            "ci_high",
        ],
    )


def penalty_sensitivity(
    records: pd.DataFrame, penalties: tuple[float, ...] = (0.0, 0.01, 0.1, 1.0)
) -> pd.DataFrame:
    from marketlens.config import finite

    rows = []
    for penalty in penalties:
        finite("penalty_per_share", penalty)
        scored = records.copy()
        scored["score"] = np.where(
            scored.filled,
            scored.implementation_shortfall,
            scored.opportunity_cost + scored.quantity * penalty,
        )
        for (scenario, policy), group in scored.groupby(["scenario", "policy"], sort=False):
            rows.append(
                dict(
                    scenario=scenario,
                    policy=policy,
                    penalty_per_share=penalty,
                    mean_cost=float(group.score.mean()),
                    completion_rate=float(group.filled.mean()),
                )
            )
    return pd.DataFrame(rows)


def joint_fill_comparisons(records: pd.DataFrame) -> pd.DataFrame:
    """Actual paired filled-cost differences; never assign zero fill cost to an unfilled order."""
    rows = []
    for scenario, group in records.groupby("scenario", sort=False):
        base = group[group.policy == "Always Execute"].set_index("seed")
        if base.empty:
            continue
        for policy in group.policy.unique():
            if policy == "Always Execute":
                continue
            other = group[group.policy == policy].set_index("seed")
            pairs = other.merge(
                base, left_index=True, right_index=True, suffixes=("_policy", "_base"), how="left"
            )
            joint = pairs[pairs.filled_policy & pairs.filled_base]
            delta = joint.implementation_shortfall_policy - joint.implementation_shortfall_base
            low, high = mean_interval(delta.to_numpy(dtype=float))
            rows.append(
                dict(
                    scenario=scenario,
                    policy=policy,
                    matched_seeds=len(pairs),
                    joint_fills=len(joint),
                    mean_difference=float(delta.mean()) if len(joint) else None,
                    ci_low=low,
                    ci_high=high,
                    lower_cost_pairs=int((delta < -1e-9).sum()),
                    higher_cost_pairs=int((delta > 1e-9).sum()),
                )
            )
    return pd.DataFrame(
        rows,
        columns=[
            "scenario",
            "policy",
            "matched_seeds",
            "joint_fills",
            "mean_difference",
            "ci_low",
            "ci_high",
            "lower_cost_pairs",
            "higher_cost_pairs",
        ],
    )
