"""Reproducible CSV/JSON exports and command-line experiment runner."""

import argparse
import json
import platform
from importlib.metadata import version
from pathlib import Path

from marketlens import __version__
from marketlens.config import FaultConfig, Interval, MarketConfig, OrderConfig, PolicyConfig, Regime
from marketlens.experiments import ExperimentResult, Scenario, run_experiment, scenario_suite


def export_result(result: ExperimentResult, directory: str | Path) -> Path:
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("records", "summary", "paired", "sensitivity"):
        getattr(result, name).to_csv(destination / f"{name}.csv", index=False)
    manifest = reproducibility_manifest(result.manifest)
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n"
    )
    return destination


def reproducibility_manifest(manifest: dict) -> dict:
    manifest = dict(manifest)
    manifest["software"] = dict(
        marketlens=__version__,
        python=platform.python_version(),
        **{p: version(p) for p in ("numpy", "pandas", "scipy")},
    )
    return manifest


def scenarios_from_manifest(manifest: dict) -> tuple[Scenario, ...]:
    scenarios = []
    for raw in manifest["scenarios"]:
        market = dict(raw["market"])
        market["regime"] = Regime(market["regime"])
        faults = dict(raw["faults"])
        for key in ("stale_intervals", "outage_intervals"):
            faults[key] = tuple(Interval(**i) for i in faults[key])
        scenarios.append(
            Scenario(
                raw["name"],
                MarketConfig(**market),
                FaultConfig(**faults),
                OrderConfig(**raw["order"]),
                PolicyConfig(**raw["policy"]),
                raw["decision_step_ms"],
            )
        )
    return tuple(scenarios)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run matched synthetic MarketLens trials")
    parser.add_argument(
        "--suite",
        choices=[
            "latency",
            "missing",
            "volatility",
            "liquidity",
            "combined",
            "thresholds",
            "heatmap",
        ],
        default="latency",
    )
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--penalty", type=float, default=0.1)
    parser.add_argument("--output", type=Path, default=Path("results/latest"))
    parser.add_argument("--manifest", type=Path, help="Replay a saved standard-policy run")
    args = parser.parse_args()
    policy_names = None
    if args.manifest:
        saved = json.loads(args.manifest.read_text())
        if saved["policies"] != "standard_policies_per_scenario":
            parser.error("CLI replay supports standard policies only")
        policy_names = saved.get("policy_names")
        scenarios, seeds, penalty = (
            scenarios_from_manifest(saved),
            saved["seeds"],
            saved["penalty_per_share"],
        )
    else:
        if args.trials < 1 or args.seed < 0:
            parser.error("trials must be positive and seed nonnegative")
        scenarios = scenario_suite(args.suite)
        seeds, penalty = tuple(range(args.seed, args.seed + args.trials)), args.penalty
    try:
        result = run_experiment(scenarios, seeds, penalty, policy_names=policy_names)
    except ValueError as error:
        parser.error(str(error))
    export_result(result, args.output)
    print(result.summary.to_string(index=False))
    print(f"Exported {len(result.records)} actual trial-policy outcomes to {args.output}")


if __name__ == "__main__":
    main()
