# MarketLens product strategy case study

## 1. Executive summary

MarketLens helps a hypothetical trading operations team examine how unreliable
market data changes execution trade-offs. Its value proposition is transparent,
reproducible scenario analysis: compare completion, costs, delay and uncertainty
without confusing stale information with executable prices. This is a portfolio
research prototype, not a validated commercial product or trading recommendation.

## 2. Problem definition

A recent-looking price can be old at its source. Immediate submission accepts
price uncertainty; waiting may obtain fresher information but introduces missed
execution risk. A low cost conditional on fills can conceal poor completion.
The product makes these competing outcomes visible rather than optimizing one
misleading headline number.

## 3. User personas

Primary: a hypothetical trading operations analyst investigating feed reliability
and documenting execution incidents. Secondary: quantitative researchers comparing
rules, trading engineers validating delivery semantics, risk analysts examining
non-execution, and internal-tool product managers prioritizing safeguards. These
are design assumptions, not interview findings.

## 4. User journey

Configure a market and order → introduce controlled faults → inspect source and
observed timelines → run matched policy trials → compare completion/cost/delay →
inspect an individual decision's available information → vary thresholds and
penalties → export records and configuration → document a qualified recommendation.

## 5. Product requirements

Functional: seeded markets; controlled latency/loss/staleness/outages; observation
isolation; four explained policies; consistent buy-side costs; matched experiments;
repeated-trial statistics; seven research views; CSV/JSON export; methodology.
Non-functional: reproducibility within recorded software versions, explicit units,
validated inputs, testable boundaries, no hidden ground-truth policy access,
truthful evidence labels and a maintainable UI-independent domain package.

## 6. Prioritisation: impact versus effort

| Feature | Expected user impact | Relative effort | Rationale |
| --- | --- | --- | --- |
| Causal observation boundary and tests | High | Medium | Foundational research validity |
| Matched policy outcomes and completion | High | Medium | Core analytical task |
| Decision trace and age timeline | High | Medium | Explains why a rule acted |
| Repeat trials and exports | High | Medium | Supports reproducible investigation |
| Simple research dashboard | Medium | Medium | Makes the workflow accessible |
| Calibrated depth and partial fills | Potentially high | High | Requires data and validation |
| Live broker integration | Unproven | Very high | Outside research prototype scope |

Ratings are design judgments, not measured RICE scores. No invented reach,
conversion, adoption or revenue numbers are used.

## 7. Success metrics

Product-quality metrics: required scenario coverage, deterministic replay checks,
matched-policy completeness, decision trace availability, interaction-test results,
export replay success and measured experiment runtime. Dashboard usability would
need task-based user evaluation; none has been conducted. Set runtime targets only
after measuring the target environment. Simulated trading metrics (shortfall,
completion, delay, p95 and opportunity cost) evaluate model outcomes, not product
adoption or business success.

## 8. Strategic trade-offs

Speed versus accuracy: preview provides quick feedback but weak evidence.
Execution versus non-execution: pausing can reduce exposure but hide opportunity
cost; display both. Automation versus oversight: transparent rules make review
possible; this application does not place real trades. Simplicity versus realism:
GBM and fixed faults aid attribution but limit external validity. Performance versus
explainability: retain individual decision traces for inspection, while summary
experiments avoid storing every trace.

## 9. Roadmap

MVP: deterministic simulation, faults, four policies, execution accounting, matched
trials, exports and a seven-view research UI. Near term: realistic variable latency,
correlated outages, partial-fill research, stronger static typing, packaging docs
with built distributions, and user-tested information hierarchy. Longer term:
licensed-data calibration, alternative dynamics, venue-specific execution, API or
SQLite persistence and independent risk validation. These remain proposals.

## 10. Limitations and next steps

No validated demand, user interviews, commercial outcomes or real-world performance
claims. The next product decision should be informed by actual task-based testing
with intended users and reproducible scenario findings. Before any operational
role, resolve the model, market-data, risk and security limitations documented in
`limitations.md`. Real trading requires substantially more than this prototype.
