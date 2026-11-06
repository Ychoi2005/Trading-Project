"""Ground-truth execution and causal orchestration, never injected into policies."""

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

from marketlens.config import OrderConfig, integer
from marketlens.events import Delivery, MarketEvent
from marketlens.observations import Observation, ObservationCursor
from marketlens.policies import Action, Decision, Policy


@dataclass(frozen=True)
class Fill:
    time_ms: int
    quantity: float
    mid: float
    execution_price: float
    spread_cost: float
    impact_cost: float
    fees: float
    implementation_shortfall: float


@dataclass(frozen=True)
class TraceEvent:
    observation: Observation
    decision: Decision


@dataclass(frozen=True)
class Evaluation:
    policy: str
    benchmark_price: float
    fill: Fill | None
    reason: str
    end_time_ms: int
    execution_delay_ms: int | None
    opportunity_cost: float
    trace: tuple[TraceEvent, ...]

    def penalized_cost(self, penalty_per_share: float, quantity: float) -> float:
        from marketlens.config import finite

        finite("penalty_per_share", penalty_per_share)
        return (
            self.fill.implementation_shortfall
            if self.fill is not None
            else self.opportunity_cost + penalty_per_share * quantity
        )


class TruthPath:
    """Evaluation-only path, piecewise constant between market updates."""

    def __init__(self, events: Sequence[MarketEvent]):
        if not events:
            raise ValueError("ground-truth path cannot be empty")
        self.events = tuple(events)
        self.times = tuple(e.event_time_ms for e in events)
        if self.times[0] != 0 or any(
            a >= b for a, b in zip(self.times, self.times[1:], strict=False)
        ):
            raise ValueError("truth must start at zero and have increasing timestamps")

    @property
    def horizon_ms(self) -> int:
        return self.times[-1]

    def at(self, time_ms: int) -> MarketEvent:
        integer("time_ms", time_ms)
        if time_ms > self.horizon_ms:
            raise ValueError("execution time outside simulated horizon")
        return self.events[bisect_right(self.times, time_ms) - 1]


def execute_buy(
    state: MarketEvent, time_ms: int, order: OrderConfig, benchmark_price: float
) -> Fill | None:
    """All-or-none; displayed liquidity is a capacity limit, not an order book."""
    integer("time_ms", time_ms)
    if state.event_time_ms > time_ms:
        raise ValueError("execution cannot use a future market state")
    if not order.arrival_ms <= time_ms <= order.deadline_ms:
        raise ValueError("execution must occur between arrival and deadline")
    if state.ask_liquidity <= 0 or order.quantity > state.ask_liquidity:
        return None
    impact_per_share = order.impact_coefficient * order.quantity / state.ask_liquidity
    price = state.mid + state.spread / 2 + impact_per_share
    spread = order.quantity * state.spread / 2
    impact = order.quantity * impact_per_share
    fees = order.quantity * order.fee_per_share
    shortfall = order.quantity * (price - benchmark_price) + fees
    if not all(isfinite(x) for x in (price, spread, impact, fees, shortfall)):
        raise ValueError("execution costs exceed numeric precision; reduce order or impact")
    return Fill(time_ms, order.quantity, state.mid, price, spread, impact, fees, shortfall)


def evaluate_policy(
    events: Sequence[MarketEvent],
    deliveries: Sequence[Delivery],
    policy: Policy,
    order: OrderConfig,
    decision_step_ms: int = 50,
) -> Evaluation:
    integer("decision_step_ms", decision_step_ms, 1)
    truth = TruthPath(events)
    if order.arrival_ms > truth.horizon_ms:
        raise ValueError("order arrival must not exceed simulation horizon")
    end = min(order.deadline_ms, truth.horizon_ms)
    benchmark = order.benchmark_price or truth.at(order.arrival_ms).mid
    # Opportunity cost: extra mid-price spend for buying at the common evaluation
    # endpoint instead of arrival, floored at zero. Not a realized fill or a fee.
    opportunity = max(truth.at(end).mid - benchmark, 0) * order.quantity
    if not isfinite(opportunity):
        raise ValueError("counterfactual opportunity cost exceeds numeric precision")
    clock = set(range(order.arrival_ms, end + 1, decision_step_ms))
    clock.update((order.arrival_ms, end))
    clock.update(
        d.delivery_time_ms for d in deliveries if order.arrival_ms <= d.delivery_time_ms <= end
    )
    for boundary in (
        order.arrival_ms + policy.config.max_wait_ms,
        order.arrival_ms + policy.config.pause_after_ms,
    ):
        if boundary <= end:
            clock.add(boundary)
    # Include exact silence deadlines even if they fall between regular ticks.
    clock.update(
        d.delivery_time_ms + policy.config.pause_after_ms
        for d in deliveries
        if order.arrival_ms <= d.delivery_time_ms + policy.config.pause_after_ms <= end
    )
    cursor = ObservationCursor(deliveries)
    trace = []
    reason = "Deadline reached" if end == order.deadline_ms else "Simulation horizon reached"
    for time_ms in sorted(clock):
        obs = cursor.at(time_ms)
        decision = policy.decide(obs, time_ms - order.arrival_ms)
        trace.append(TraceEvent(obs, decision))
        if decision.action == Action.EXECUTE:
            fill = execute_buy(truth.at(time_ms), time_ms, order, benchmark)
            return Evaluation(
                policy.name,
                benchmark,
                fill,
                decision.reason if fill else "Insufficient ask liquidity",
                time_ms,
                time_ms - order.arrival_ms if fill else None,
                0.0 if fill else opportunity,
                tuple(trace),
            )
        if decision.action == Action.PAUSE:
            return Evaluation(
                policy.name,
                benchmark,
                None,
                decision.reason,
                time_ms,
                None,
                opportunity,
                tuple(trace),
            )
    return Evaluation(policy.name, benchmark, None, reason, end, None, opportunity, tuple(trace))
