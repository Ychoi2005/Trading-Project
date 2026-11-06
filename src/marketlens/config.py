"""Validated, immutable configuration. Times are relative integer milliseconds."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from numbers import Real


class Regime(StrEnum):
    STABLE = "stable"
    HIGH_VOLATILITY = "high_volatility"
    LOW_LIQUIDITY = "low_liquidity"


def finite(name: str, value: float, minimum: float = 0, *, positive: bool = False) -> None:
    if (
        not isinstance(value, Real)
        or isinstance(value, bool)
        or not isfinite(value)
        or value < minimum
        or (positive and value == 0)
    ):
        raise ValueError(f"{name} must be finite and {'positive' if positive else f'>= {minimum}'}")


def integer(name: str, value: int, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


@dataclass(frozen=True)
class MarketConfig:
    initial_price: float = 100.0
    duration_ms: int = 10_000
    step_ms: int = 50
    drift: float = 0.0
    volatility: float = 0.2
    spread: float = 0.02
    liquidity: float = 1000.0
    seed: int = 42
    regime: Regime = Regime.STABLE

    def __post_init__(self) -> None:
        finite("initial_price", self.initial_price, positive=True)
        finite("volatility", self.volatility)
        finite("spread", self.spread)
        finite("liquidity", self.liquidity)
        finite("drift", self.drift, minimum=-float("inf"))
        integer("duration_ms", self.duration_ms)
        integer("step_ms", self.step_ms, 1)
        integer("seed", self.seed)
        if self.duration_ms % self.step_ms:
            raise ValueError("duration_ms must be divisible by step_ms")
        if self.duration_ms // self.step_ms > 1_000_000:
            raise ValueError("at most 1,000,001 market events are supported")
        if not isinstance(self.regime, Regime):
            raise ValueError("regime must be a Regime")
        finite("effective volatility", self.effective_volatility)
        finite("effective spread", self.effective_spread)

    @property
    def effective_volatility(self) -> float:
        return self.volatility * (3 if self.regime == Regime.HIGH_VOLATILITY else 1)

    @property
    def effective_spread(self) -> float:
        return (
            self.spread
            * {Regime.STABLE: 1, Regime.HIGH_VOLATILITY: 2, Regime.LOW_LIQUIDITY: 3}[self.regime]
        )

    @property
    def effective_liquidity(self) -> float:
        return self.liquidity * (0.1 if self.regime == Regime.LOW_LIQUIDITY else 1)


@dataclass(frozen=True)
class Interval:
    """Half-open interval [start_ms, end_ms)."""

    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        integer("start_ms", self.start_ms)
        integer("end_ms", self.end_ms)
        if self.end_ms <= self.start_ms:
            raise ValueError("interval end must exceed start")

    def contains(self, time_ms: int) -> bool:
        return self.start_ms <= time_ms < self.end_ms


@dataclass(frozen=True)
class FaultConfig:
    latency_ms: int = 0
    missing_probability: float = 0.0
    stale_intervals: tuple[Interval, ...] = ()
    outage_intervals: tuple[Interval, ...] = ()
    seed: int = 31415

    def __post_init__(self) -> None:
        integer("latency_ms", self.latency_ms)
        integer("seed", self.seed)
        finite("missing_probability", self.missing_probability)
        if self.missing_probability > 1:
            raise ValueError("missing_probability must be <= 1")
        for name in ("stale_intervals", "outage_intervals"):
            intervals = getattr(self, name)
            if not isinstance(intervals, tuple) or any(
                not isinstance(i, Interval) for i in intervals
            ):
                raise ValueError(f"{name} must be a tuple of Interval values")


@dataclass(frozen=True)
class OrderConfig:
    arrival_ms: int = 1000
    deadline_ms: int = 5000
    quantity: float = 100.0
    fee_per_share: float = 0.001
    impact_coefficient: float = 0.01
    benchmark_price: float | None = None

    def __post_init__(self) -> None:
        integer("arrival_ms", self.arrival_ms)
        integer("deadline_ms", self.deadline_ms)
        if self.deadline_ms < self.arrival_ms:
            raise ValueError("deadline must be >= arrival")
        finite("quantity", self.quantity, positive=True)
        finite("fee_per_share", self.fee_per_share)
        finite("impact_coefficient", self.impact_coefficient)
        if self.benchmark_price is not None:
            finite("benchmark_price", self.benchmark_price, positive=True)


@dataclass(frozen=True)
class PolicyConfig:
    freshness_ms: int = 100
    max_wait_ms: int = 500
    pause_after_ms: int = 1000
    max_spread: float = 0.1
    max_sequence_gap: int = 5
    timeout_execute: bool = False

    def __post_init__(self) -> None:
        for name in ("freshness_ms", "max_wait_ms", "pause_after_ms", "max_sequence_gap"):
            integer(name, getattr(self, name))
        finite("max_spread", self.max_spread)
        if not isinstance(self.timeout_execute, bool):
            raise ValueError("timeout_execute must be bool")
