# Reproducing experiments

From the checkout root after editable installation:

```sh
marketlens-experiment --suite latency --trials 100 --seed 42 --output results/latency
marketlens-experiment --suite missing --trials 100 --seed 42 --output results/missing
marketlens-experiment --suite volatility --trials 100 --seed 42 --output results/volatility
marketlens-experiment --suite liquidity --trials 100 --seed 42 --output results/liquidity
marketlens-experiment --suite combined --trials 100 --seed 42 --output results/combined
marketlens-experiment --suite thresholds --trials 100 --seed 42 --output results/thresholds
marketlens-experiment --manifest results/latency/manifest.json --output results/replay
```

Each output contains `records.csv`, `summary.csv`, `paired.csv`, `sensitivity.csv`
and `manifest.json`. Records contain one row per scenario/seed/policy, including
path hash, actual fault seed, benchmark, fill status and cost components. Blank
execution fields indicate unfilled orders. Manifests include complete scenario
parameters, seed lists, penalty, schema and software versions. Exports overwrite
files in the selected directory; choose separate directories to retain runs.
CLI replay supports the built-in policies; custom policy classes are not serialized.

The dashboard provides preview (10 trials), full runs (100 default), all suites
and a volatility × latency heatmap. Changing controls invalidates displayed saved
comparisons until rerun. Product Insights explicitly uses the last executed run.
Download its manifest to preserve configuration. For custom settings use the
Python API: construct `Scenario` values and call `run_experiment`.

Interpret completion and conditional filled costs together. Penalty-adjusted
comparisons and sensitivity curves are assumption-dependent. Preview results,
identical policy outcomes, or intervals including zero are not evidence of a
profitable strategy. No broad policy superiority is asserted by this project.

Actual verification runs and commands are recorded in `verification.md` after
execution. No experiment findings should be inferred from documentation examples.

## Product experience experiments (schema 2)

The legacy latency sweep is primarily a rule check: fixed latency above a policy's
age limit makes fresh data unattainable. That outcome validates implementation,
but does not establish an execution advantage. Healthy-market ties are valuable
controls and remain visible.

New suites start from the declared reliability demonstration unless a Python caller
supplies a different base. The UI uses its currently configured base. CLI defaults
retain seed 42 and use 100 independent trials; no seed was chosen to favor a policy.

```sh
marketlens-experiment --suite tradeoffs --trials 100 --seed 42 --output results/product_tradeoffs
marketlens-experiment --suite waiting --trials 100 --seed 42 --output results/waiting
marketlens-experiment --suite urgency --trials 100 --seed 42 --output results/urgency
marketlens-experiment --suite volatility_latency --trials 100 --seed 42 --output results/volatility_latency
```

- `tradeoffs`: healthy control, intermittent feed, urgent deadline, insufficient
  liquidity, and explicitly labelled unattainable-freshness rule check.
- `waiting`: 0/200/750/1500 ms maximum waiting budgets on identical paths.
- `urgency`: 100/300/1000 ms execution deadlines after arrival, on identical paths.
- `volatility_latency`: 3 annualised volatility levels × 3 fixed latencies, retaining
  intermittent missing updates and the demo outage. Policy rules do not see future
  volatility realizations; timing and cost dispersion should be interpreted separately.

All four suites were executed with 100 seeds, producing **8,400 new trial-policy
outcomes**, in addition to the legacy artifacts. See each directory's manifest.
They are controlled, uncalibrated experiments, not real-world performance evidence.

### Findings from those runs

In `product_tradeoffs`, the healthy control filled all policies at identical costs.
Under intermittent reliability, Always Execute filled 100/100 at mean shortfall
$1.20. Wait for Fresh Data filled 100/100 with mean shortfall $1.287376 and 221 ms
mean delay. Its paired cost difference was +$0.087376, 95% Student-t interval
[-$0.038492, +$0.213245]. Waiting was cheaper in 42 seeds and more expensive in 58.
Adaptive filled 97/100; among the 97 joint fills it was cheaper in 44 and more
expensive in 53. Its paired mean difference was +$0.107978, interval
[-$0.022282, +$0.238238]. Neither interval establishes a mean-cost advantage.
Guardrail filled none in this deliberately stale-at-arrival scenario; its filled
cost is undefined. These findings include both favorable and unfavorable paths.

In `waiting`, extending the wait budget from 200 to 750 ms raised Wait for Fresh
Data completion from 69% to 100%. Extending it again to 1500 ms did not improve
completion or mean filled cost in these 100 seeds. Adaptive remained at 97% because
its separate silence/quality rules still apply. More time is not automatically
more information or a better cost.

In `urgency`, a 100 ms deadline after arrival left no time for the scheduled recovery;
only Always Execute completed. At 300 ms, Wait for Fresh Data completed 99%, and
Adaptive 73%; at 1000 ms they completed 100% and 97%. Some of this contrast follows
the scheduled outage boundary; variation after recovery comes from the missing
updates. The half-capacity liquidity case filled no policy, demonstrating a venue
capacity assumption rather than a policy failure that waiting can fix.

The new `joint_fills.csv` compares realized shortfall on seeds where both the
policy and baseline filled. It never substitutes a zero execution cost for an
unfilled order. Such comparisons are still conditional on a selected subset;
completion, unfilled opportunity cost and penalty sensitivity remain mandatory.
Schema-2 records also include observable submission-age and pending exposure
metrics. Legacy schema-1 artifacts are retained unchanged; replay preserves their
shared execution columns, while new export columns and intervals may differ.
