"""A monotonic observation cursor; policies only receive immutable snapshots."""

from collections.abc import Sequence
from dataclasses import dataclass

from marketlens.config import integer
from marketlens.events import Delivery, ObservedQuote


@dataclass(frozen=True)
class Observation:
    time_ms: int
    quote: ObservedQuote | None
    received_count: int
    last_sequence_gap: int

    @property
    def quote_age_ms(self) -> int | None:
        return None if self.quote is None else self.time_ms - self.quote.event_time_ms

    @property
    def since_delivery_ms(self) -> int | None:
        return None if self.quote is None else self.time_ms - self.quote.delivery_time_ms


class ObservationCursor:
    """Consume only deliveries at or before the requested timestamp, ties included."""

    def __init__(self, deliveries: Sequence[Delivery]):
        self._deliveries = tuple(deliveries)
        previous_time, previous_id = -1, -1
        for delivery in self._deliveries:
            q = delivery.quote
            if q.delivery_time_ms < q.event_time_ms or q.event_time_ms < 0:
                raise ValueError("delivery cannot precede nonnegative event time")
            if q.delivery_time_ms < previous_time or q.event_id <= previous_id:
                raise ValueError("deliveries must be time-ordered with increasing source IDs")
            previous_time, previous_id = q.delivery_time_ms, q.event_id
        self._index = 0
        self._time = -1
        self._quote: ObservedQuote | None = None
        self._gap = 0

    def at(self, time_ms: int) -> Observation:
        integer("time_ms", time_ms)
        if time_ms < self._time:
            raise ValueError("observation clock cannot move backwards")
        self._time = time_ms
        while (
            self._index < len(self._deliveries)
            and self._deliveries[self._index].delivery_time_ms <= time_ms
        ):
            q = self._deliveries[self._index].quote
            self._gap = q.event_id if self._quote is None else q.event_id - self._quote.event_id - 1
            self._quote = q
            self._index += 1
        return Observation(time_ms, self._quote, self._index, self._gap)
