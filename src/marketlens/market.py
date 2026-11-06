"""Single-asset geometric Brownian motion with explicit annualisation."""

import math

import numpy as np

from marketlens.config import MarketConfig
from marketlens.events import MarketEvent

MS_PER_YEAR = 365.25 * 24 * 60 * 60 * 1000


def simulate_market(config: MarketConfig) -> tuple[MarketEvent, ...]:
    """Include t=0 and the horizon; reject numerically unrepresentable paths."""
    rng = np.random.default_rng(config.seed)
    count = config.duration_ms // config.step_ms
    dt = config.step_ms / MS_PER_YEAR
    sigma = np.float64(config.effective_volatility)
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        increments = (config.drift - 0.5 * sigma**2) * dt + sigma * math.sqrt(
            dt
        ) * rng.standard_normal(count)
        prices = config.initial_price * np.exp(np.r_[0.0, np.cumsum(increments)])
    if not np.all(np.isfinite(prices) & (prices > 0)):
        raise ValueError("GBM parameters produce non-finite or underflowed prices")
    half_spread = config.effective_spread / 2
    if np.any(prices <= half_spread):
        raise ValueError("spread would produce a non-positive bid; reduce spread or volatility")
    if not np.all(np.isfinite(prices + half_spread)):
        raise ValueError("ask prices overflow; reduce initial price or spread")
    return tuple(
        MarketEvent(
            i,
            i * config.step_ms,
            float(p),
            float(p - half_spread),
            float(p + half_spread),
            config.effective_spread,
            config.effective_liquidity,
            config.effective_liquidity,
            config.regime,
        )
        for i, p in enumerate(prices)
    )
