# Executed research artifacts

- `latency/`: 100 seeds (42–141), 6 settings, 4 policies, 2,400 outcomes.
- `combined/`: 100 seeds (42–141), 2 settings, 4 policies, 800 outcomes.

These directories contain actual CLI-generated outputs, not illustrative data.
`manifest.json` records all configuration, seeds and numerical library versions.
Blank execution fields denote unfilled orders. Paired cost differences depend on
an explicit non-execution penalty; `sensitivity.csv` varies it. Reproduction
commands and qualified interpretation are in `docs/experiments.md` and README.
No general performance or real-market policy superiority is claimed.


Schema-2 product experience studies (100 seeds each, 42–141):

- `product_tradeoffs/`: 5 settings × 4 policies = 2,000 outcomes.
- `waiting/`: 4 settings × 4 policies = 1,600 outcomes.
- `urgency/`: 3 settings × 4 policies = 1,200 outcomes.
- `volatility_latency/`: 9 settings × 4 policies = 3,600 outcomes.

These add 8,400 executed outcomes and `joint_fills.csv` to the legacy 3,200.
Legacy artifacts are retained, not silently regenerated. New records include
observable staleness metrics. See docs/experiments.md for evidence and limitations.
