"""Transparent policies. No truth path, future deliveries or fault schedule input."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from marketlens.config import PolicyConfig
from marketlens.observations import Observation


class Action(StrEnum):
    EXECUTE = "execute"
    WAIT = "wait"
    PAUSE = "pause"


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str


class Policy(Protocol):
    name: str
    config: PolicyConfig

    def decide(self, observation: Observation, elapsed_ms: int) -> Decision: ...


@dataclass(frozen=True)
class AlwaysExecute:
    config: PolicyConfig = PolicyConfig()
    name: str = "Always Execute"

    def decide(self, observation: Observation, elapsed_ms: int) -> Decision:
        return Decision(Action.EXECUTE, "Unconditional market-order submission, including no quote")


@dataclass(frozen=True)
class WaitForFreshData:
    config: PolicyConfig = PolicyConfig()
    name: str = "Wait for Fresh Data"

    def decide(self, observation: Observation, elapsed_ms: int) -> Decision:
        age = observation.quote_age_ms
        if age is not None and age <= self.config.freshness_ms:
            return Decision(Action.EXECUTE, "Quote age meets freshness threshold")
        if elapsed_ms >= self.config.max_wait_ms:
            if self.config.timeout_execute:
                return Decision(Action.EXECUTE, "Maximum wait reached: configured execute fallback")
            return Decision(Action.PAUSE, "Maximum wait reached: configured pause fallback")
        return Decision(Action.WAIT, "Awaiting a sufficiently fresh delivered quote")


@dataclass(frozen=True)
class DataQualityGuardrail:
    config: PolicyConfig = PolicyConfig()
    name: str = "Data Quality Guardrail"

    def decide(self, observation: Observation, elapsed_ms: int) -> Decision:
        if observation.quote is None:
            return Decision(Action.PAUSE, "No delivered quote")
        if observation.quote_age_ms > self.config.freshness_ms:
            return Decision(Action.PAUSE, "Quote is too old")
        if observation.quote.spread > self.config.max_spread:
            return Decision(Action.PAUSE, "Observed spread exceeds guardrail")
        if observation.last_sequence_gap > self.config.max_sequence_gap:
            return Decision(Action.PAUSE, "Last observable sequence gap exceeds guardrail")
        return Decision(Action.EXECUTE, "Observed data meets all guardrails")


@dataclass(frozen=True)
class AdaptiveDecisionPolicy:
    config: PolicyConfig = PolicyConfig()
    name: str = "Adaptive Decision Policy"

    def decide(self, observation: Observation, elapsed_ms: int) -> Decision:
        q = observation.quote
        if (
            q is not None
            and observation.quote_age_ms <= self.config.freshness_ms
            and q.spread <= self.config.max_spread
            and observation.last_sequence_gap <= self.config.max_sequence_gap
        ):
            return Decision(Action.EXECUTE, "Fresh quote, acceptable spread and sequence gap")
        if elapsed_ms >= self.config.max_wait_ms:
            return Decision(Action.PAUSE, "Maximum wait reached")
        silence = observation.since_delivery_ms
        if (silence is None and elapsed_ms >= self.config.pause_after_ms) or (
            silence is not None and silence >= self.config.pause_after_ms
        ):
            return Decision(Action.PAUSE, "Delivery silence exceeds safety threshold")
        return Decision(Action.WAIT, "Data quality insufficient; within waiting and safety limits")


def standard_policies(config: PolicyConfig | None = None) -> tuple[Policy, ...]:
    config = config or PolicyConfig()
    return (
        AlwaysExecute(config),
        WaitForFreshData(config),
        DataQualityGuardrail(config),
        AdaptiveDecisionPolicy(config),
    )
