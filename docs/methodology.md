# Methodology

## Market model and units

A single synthetic asset follows geometric Brownian motion:

`P(t+dt) = P(t) exp((mu - sigma²/2) dt + sigma sqrt(dt) Z)`.

`Z` comes from a local `numpy.random.default_rng(seed)`. `mu` and `sigma` are
annualised; `dt = step_ms / 31,557,600,000` (365.25 calendar days/year). Prices,
spreads and impact coefficients are currency/share; liquidity and quantity are
shares. Timestamps and delays are relative integer milliseconds. Costs are total
currency for the order, not basis points. There is no trading-calendar adjustment.

The path includes time zero and the configured horizon. Duration must be divisible
by the step. Stable uses the supplied parameters; high volatility multiplies sigma
by 3 and spread by 2; low liquidity multiplies size by 0.1 and spread by 3. Liquidity
and spread are constant within each path. Bid/ask are mid ± half-spread. Zero
liquidity is allowed; nonpositive bids and unrepresentable GBM prices raise errors.
No clipping is used to conceal invalid paths.

## Reliability model

Each source event receives one independent missingness draw. A source stale window
suppresses new quotes, preserving the last delivered quote's original timestamp.
Fixed latency moves each remaining delivery forward. A delivery outage discards
updates whose delayed arrival falls inside it. Windows are half-open `[start,end)`;
overlap is permitted. Suppressed updates are not replayed after recovery. Staleness
is silence/held observation, not a newly timestamped historical price.

The observer processes deliveries at or before the decision time and holds the
last quote. Quote age = decision time − source time; delivery silence = decision
time − last delivery time. No prior quote means unavailable data. Sequence gaps
become observable only on the next successful delivery; no hidden loss count or
future fault schedule is passed to policies. Constant latency preserves ordering.

## Decision rules

All policies implement `decide(observation, elapsed_ms)`:

| Policy | Execute | Wait | Pause |
| --- | --- | --- | --- |
| Always Execute | Immediately, even without a quote | Never | Never by policy |
| Wait for Fresh Data | Quote age ≤ freshness limit | Until max wait | At timeout, unless execute fallback configured |
| Data Quality Guardrail | Fresh quote, spread ≤ limit, last sequence gap ≤ limit | Never | Any failed check or unavailable quote |
| Adaptive Decision Policy | Same quality checks as guardrail | Quality inadequate but within wait and silence limits | Max wait or delivery-silence limit reached |

A fresh acceptable quote wins at the exact timeout boundary. With no prior quote,
adaptive silence is measured from order arrival; otherwise it uses last delivery.
Pause is terminal for this one order. These are decision-support experiments, not
a continuously resuming trading system. Always Execute is deliberately an
unconditional venue submission baseline, not an assertion that missing data is safe.

Decisions occur on a regular grid anchored at arrival, all delivered update times,
wait/silence boundaries, the inclusive deadline, and horizon. Truth is piecewise
constant between market updates. Execution at time t uses only truth at or before
t, never future interpolation. An order may time out at the horizon before its
configured deadline. Orders arriving after the horizon are invalid.

## Execution and accounting

One marketable buy, all-or-none. If ask liquidity is zero or quantity exceeds it,
the attempted order is rejected. No division by zero, partial fill, retry, queue,
or liquidity replenishment is assumed. Otherwise:

- impact/share = k × quantity / ask liquidity
- execution price = current truth mid + current truth spread/2 + impact/share
- fees = fee/share × quantity
- implementation shortfall = quantity × (execution price − benchmark) + fees

Default benchmark is the truth mid at order arrival, identical for every policy
on that path. A configured positive benchmark can override it. Spread cost, impact
cost and fees are explanatory components, not extra charges added to shortfall.
The equality is `shortfall = quantity*(execution_mid-benchmark) + spread_cost +
impact_cost + fees`. Execution price excludes fees; shortfall includes them.

For unfilled orders, execution cost and delay are undefined. Completion is reported
separately. Illustrative counterfactual opportunity cost is
`quantity * max(endpoint_mid - benchmark, 0)`, where endpoint is the minimum of
deadline and horizon, common to every policy. This approximates extra expenditure
if the buy is deferred to the endpoint. It is not a realized trade, and ignores
counterfactual spread/impact/fees. Downward price moves produce zero opportunity
cost under this convention. A sensitivity score uses filled shortfall if filled,
otherwise opportunity cost plus quantity × chosen non-execution penalty/share.
Penalty curves use 0, 0.01, 0.1 and 1 currency/share. Report this assumption-dependent
score separately from actual execution costs; zero penalty never changes the
reported unfilled status.

## Repeated trials and uncertainty

One market path and one fault stream are reused for all policies in each
scenario/seed. Fault seeds are derived with `SeedSequence([market_seed,
base_fault_seed])`, independent of market draws. Sweeps share market seeds across
settings. Default full experiments use 100 trials; UI preview uses 10. Seed count
is configurable. Reproducibility is supported for the same Python/dependency
versions; versions are recorded in CLI exports. Cross-version bit identity is not
promised. UI and CLI use the same seed derivation.

Filled-order summaries include mean, median, sample standard deviation, p95 and
the mean of samples at or above the empirical p95. Average delay is conditional
on fills. Mean shortfall uses a two-sided Student-t 95% interval; fewer than two
fills yields no interval. Completion uses Wilson 95% intervals. Paired comparisons
use per-seed penalty-adjusted cost differences versus Always Execute, then a
Student-t interval on those differences. These require independent trials and
sufficient samples; heavy tails, small samples and selection by fill can make
intervals misleading. No multiple-comparison correction or significance claim
is made. Confidence intervals are not prediction intervals.
