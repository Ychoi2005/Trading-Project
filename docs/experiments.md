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
