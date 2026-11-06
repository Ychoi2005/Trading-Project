# MarketLens implementation roadmap

The supplied MarketLens — Trading Under Uncertainty specification is the master
requirements document. All findings require executed experiments; synthetic
outcomes cannot establish real-world profitability.

## 1. Foundation and core engines

- Establish Python 3.11+ src layout, pytest, coverage, Ruff and editable installation.
- Define immutable configurations, market events, deliveries and observations.
- Document integer millisecond clocks, annualised GBM, event ordering and boundaries.
- Implement seeded GBM, three parameter presets and bid/ask liquidity.
- Implement latency, loss, stale windows, outages and causal observation delivery.
- Verify deterministic paths, positivity, spreads, edge cases and combined faults.

## 2. Decisions and execution

- Implement four interpretable policies with one observation-only input interface.
- Evaluate decision ticks plus delivery, timeout and deadline boundaries.
- Execute buys using contemporaneous truth, never historical observed prices.
- Account for spread, impact and fees once; use a shared arrival benchmark.
- Track unfilled orders and explicit penalty sensitivity separately from filled costs.
- Test look-ahead resistance, timeouts, thresholds, costs, liquidity and deadlines.

## 3. Experiments

- Share each seeded path and fault stream across policies for paired comparisons.
- Implement latency, missingness, volatility, liquidity, combined-failure and
  threshold-sensitivity suites with configurable trials (default 100) and preview.
- Store per-trial outcomes, summaries, paired differences and confidence intervals.
- Export CSV and JSON with complete parameters, seeds and dependency versions.
- Test reproducibility, statistical calculations and exported artifacts.

## 4. Dashboard

Build seven Streamlit views: Executive Overview, Market Simulation, Policy
Comparison, Scenario Stress Testing, Decision Explorer, Product Insights, and
Methodology & Limitations. Plotly consumes actual engine results. Truth is labelled
retrospective. Show completion alongside costs, explicit unfilled outcomes, export
controls and a navy/teal theme. Test rendered pages with AppTest and server HTTP
startup; browser visual inspection is a separate verification claim.

## 5. Documentation and verification

Write methodology, limitations, experiments, product strategy and macOS setup.
Execute pytest/coverage, Ruff, CLI experiments, UI interaction and HTTP startup
checks; fix diagnosed issues. Record real outcomes without invented findings.

## Risks and trade-offs

GBM omits jumps and microstructure. Parameter presets are not regime switching.
Discrete decision ticks can affect outcomes. Fixed latency and independent loss
simplify attribution but omit correlated networks. All-or-none fills simplify
execution; no replenishment or partial-fill model is claimed. Penalties for
non-execution are assumptions, so report their sensitivity alongside completion.
Dashboard scope follows the user's expanded request; no real broker integration.

## Delivered increment

All five milestones above are implemented. The source, automated checks, saved
example results and remaining limitations are described in `verification.md`.
The roadmap's future model extensions remain out of scope; this delivery is a
research prototype, not an operational trading system.
