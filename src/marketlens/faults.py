"""Fault composition: seeded loss, source staleness, latency, delivery outage."""

from collections.abc import Sequence

import numpy as np

from marketlens.config import FaultConfig
from marketlens.events import Delivery, MarketEvent, ObservedQuote


def inject_faults(events: Sequence[MarketEvent], config: FaultConfig) -> tuple[Delivery, ...]:
    """Suppressed updates are discarded, never buffered or delivered as fresh quotes."""
    rng = np.random.default_rng(config.seed)
    deliveries = []
    previous_time = -1
    previous_id = -1
    for event in events:
        if event.event_time_ms <= previous_time or event.event_id <= previous_id:
            raise ValueError("source events must have strictly increasing timestamps and IDs")
        previous_time, previous_id = event.event_time_ms, event.event_id
        missing = rng.random() < config.missing_probability  # one draw per source event
        stale = any(i.contains(event.event_time_ms) for i in config.stale_intervals)
        delivery_time = event.event_time_ms + config.latency_ms
        outage = any(i.contains(delivery_time) for i in config.outage_intervals)
        if missing or stale or outage:
            continue
        quote = ObservedQuote(
            event.event_id,
            event.event_time_ms,
            delivery_time,
            event.mid,
            event.bid,
            event.ask,
            event.spread,
            event.bid_liquidity,
            event.ask_liquidity,
            event.regime,
        )
        deliveries.append(Delivery(quote))
    return tuple(deliveries)
