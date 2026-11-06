"""Source events and delivery envelopes are immutable and separately represented."""

from dataclasses import dataclass

from marketlens.config import Regime


@dataclass(frozen=True)
class MarketEvent:
    event_id: int
    event_time_ms: int
    mid: float
    bid: float
    ask: float
    spread: float
    bid_liquidity: float
    ask_liquidity: float
    regime: Regime


@dataclass(frozen=True)
class ObservedQuote:
    event_id: int
    event_time_ms: int
    delivery_time_ms: int
    mid: float
    bid: float
    ask: float
    spread: float
    bid_liquidity: float
    ask_liquidity: float
    regime: Regime


@dataclass(frozen=True)
class Delivery:
    quote: ObservedQuote

    @property
    def delivery_time_ms(self) -> int:
        return self.quote.delivery_time_ms
