"""Matched scenarios: one truth path and delivery stream per scenario and seed."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace

import numpy as np
import pandas as pd

from marketlens.config import (
    FaultConfig,
    Interval,
    MarketConfig,
    OrderConfig,
    PolicyConfig,
    Regime,
    finite,
    integer,
)
from marketlens.execution import evaluate_policy
from marketlens.faults import inject_faults
from marketlens.market import simulate_market
from marketlens.metrics import paired_comparisons, penalty_sensitivity, summarize
from marketlens.policies import Policy, standard_policies


@dataclass(frozen=True)
class Scenario:
    name: str = "Configured scenario"
    market: MarketConfig = MarketConfig()
    faults: FaultConfig = FaultConfig()
    order: OrderConfig = OrderConfig()
    policy: PolicyConfig = PolicyConfig()
    decision_step_ms: int = 50

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("scenario name cannot be empty")
        integer("decision_step_ms", self.decision_step_ms, 1)
        if self.order.arrival_ms > self.market.duration_ms:
            raise ValueError("order arrival must not exceed market horizon")


@dataclass
class ExperimentResult:
    records: pd.DataFrame
    summary: pd.DataFrame
    paired: pd.DataFrame
    sensitivity: pd.DataFrame
    manifest: dict


def fault_seed(seed: int, base_seed: int) -> int:
    return int(np.random.SeedSequence([seed, base_seed]).generate_state(1)[0])


def run_experiment(
    scenarios: Sequence[Scenario],
    seeds: Sequence[int] = tuple(range(100)),
    penalty_per_share: float = 0.1,
    policies: Sequence[Policy] | None = None,
    policy_names: Sequence[str] | None = None,
) -> ExperimentResult:
    finite("penalty_per_share", penalty_per_share)
    if policies is not None and policy_names is not None:
        raise ValueError("choose custom policies or built-in policy names, not both")
    if not scenarios or len({s.name for s in scenarios}) != len(scenarios):
        raise ValueError("provide nonempty, uniquely named scenarios")
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("provide nonempty, unique seeds")
    for seed in seeds:
        integer("seed", seed)
    rows = []
    for scenario in scenarios:
        selected = tuple(policies) if policies is not None else standard_policies(scenario.policy)
        if policy_names is not None:
            if (
                not policy_names
                or len(set(policy_names)) != len(policy_names)
                or set(policy_names) - {p.name for p in selected}
            ):
                raise ValueError("provide unique, known built-in policy names")
            selected = tuple(p for p in selected if p.name in policy_names)
        if not selected or len({p.name for p in selected}) != len(selected):
            raise ValueError("provide nonempty, uniquely named policies")
        for seed in seeds:
            market = replace(scenario.market, seed=seed)
            faults = replace(scenario.faults, seed=fault_seed(seed, scenario.faults.seed))
            events = simulate_market(market)
            deliveries = inject_faults(events, faults)
            path_id = hashlib.sha256(
                json.dumps([asdict(e) for e in events], sort_keys=True).encode()
            ).hexdigest()
            for policy in selected:
                outcome = evaluate_policy(
                    events, deliveries, policy, scenario.order, scenario.decision_step_ms
                )
                f = outcome.fill
                rows.append(
                    dict(
                        scenario=scenario.name,
                        seed=seed,
                        fault_seed=faults.seed,
                        path_id=path_id,
                        policy=policy.name,
                        filled=f is not None,
                        quantity=scenario.order.quantity,
                        benchmark_price=outcome.benchmark_price,
                        execution_time_ms=f.time_ms if f else None,
                        execution_delay_ms=outcome.execution_delay_ms,
                        execution_price=f.execution_price if f else None,
                        spread_cost=f.spread_cost if f else None,
                        impact_cost=f.impact_cost if f else None,
                        fees=f.fees if f else None,
                        implementation_shortfall=f.implementation_shortfall if f else None,
                        opportunity_cost=outcome.opportunity_cost,
                        penalized_cost=outcome.penalized_cost(
                            penalty_per_share, scenario.order.quantity
                        ),
                        reason=outcome.reason,
                    )
                )
    records = pd.DataFrame(rows)
    manifest = dict(
        schema_version=1,
        scenarios=[asdict(s) for s in scenarios],
        seeds=list(seeds),
        penalty_per_share=penalty_per_share,
        policy_names=list(policy_names) if policy_names is not None else None,
        policies=(
            [dict(name=p.name, config=asdict(p.config)) for p in policies]
            if policies is not None
            else "standard_policies_per_scenario"
        ),
    )
    return ExperimentResult(
        records,
        summarize(records),
        paired_comparisons(records),
        penalty_sensitivity(records),
        manifest,
    )


def scenario_suite(kind: str, base: Scenario | None = None) -> tuple[Scenario, ...]:
    """Suites A–F; seeds shared across settings as well as policies."""
    base = base or Scenario()
    if kind == "latency":
        return tuple(
            replace(base, name=f"Latency {v} ms", faults=replace(base.faults, latency_ms=v))
            for v in (0, 50, 100, 250, 500, 1000)
        )
    if kind == "missing":
        return tuple(
            replace(
                base, name=f"Missing {v:.0%}", faults=replace(base.faults, missing_probability=v)
            )
            for v in (0, 0.1, 0.3, 0.6, 1.0)
        )
    if kind == "volatility":
        return tuple(
            replace(
                base,
                name=f"Volatility {v}",
                market=replace(base.market, volatility=v, regime=Regime.STABLE),
            )
            for v in (0.1, 0.3, 0.8)
        )
    if kind == "liquidity":
        return tuple(
            replace(
                base,
                name=f"Liquidity {v}",
                market=replace(base.market, liquidity=v, regime=Regime.LOW_LIQUIDITY),
            )
            for v in (10000, 1000, 100, 0)
        )
    if kind == "combined":
        return (
            base,
            replace(
                base,
                name="Combined failures",
                market=replace(base.market, regime=Regime.LOW_LIQUIDITY),
                faults=FaultConfig(
                    latency_ms=500, missing_probability=0.3, outage_intervals=(Interval(900, 1800),)
                ),
            ),
        )
    if kind == "thresholds":
        return tuple(
            replace(
                base,
                name=f"Fresh {fresh} / Wait {wait} ms",
                policy=replace(base.policy, freshness_ms=fresh, max_wait_ms=wait),
            )
            for fresh in (50, 100, 500)
            for wait in (100, 500, 1000)
        )
    if kind == "heatmap":
        return tuple(
            replace(
                base,
                name=f"Vol {vol} / Latency {lat}",
                market=replace(base.market, volatility=vol, regime=Regime.STABLE),
                faults=replace(base.faults, latency_ms=lat),
            )
            for vol in (0.1, 0.3, 0.8)
            for lat in (0, 100, 500)
        )
    raise ValueError(f"unknown scenario suite: {kind}")
