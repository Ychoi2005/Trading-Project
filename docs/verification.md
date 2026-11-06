# Verification record

Verified on 7 November 2026 (Australia/Sydney), using Linux and Python 3.12.14.
This records executed checks, not performance targets or real-market findings.

| Check | Actual outcome |
| --- | --- |
| Editable package installation with development extras | Succeeded |
| Exact-version dependency installation from requirements-lock.txt | Succeeded |
| pip check | No broken requirements |
| pytest with coverage | 93 passed; 0 failed; no skipped tests |
| Statement coverage | 816 / 828 statements, reported as 99% (not branch coverage) |
| Ruff lint | All checks passed |
| Ruff format check | 21 files already formatted |
| Streamlit AppTest | All seven views and comparison, configuration invalidation, heatmap, decision inspection, all-missing/zero-liquidity and policy-selection interactions passed |
| Streamlit HTTP startup | Health endpoint and root returned HTTP 200 |
| Latency experiment | 100 seeds × 6 settings × 4 policies = 2,400 outcomes |
| Combined-failure experiment | 100 seeds × 2 settings × 4 policies = 800 outcomes |
| Final-code latency replay | records, summary, paired, sensitivity and manifest artifacts byte-identical |

## Commands executed

```sh
python -m pip install -e '.[dev]'
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps -e .
python -m pip check
ruff format --check src tests app
ruff check src tests app
python -m pytest --cov=marketlens --cov-report=term-missing -q
python -m marketlens.reporting --suite latency --trials 100 --seed 42 --output results/latency
python -m marketlens.reporting --suite combined --trials 100 --seed 42 --output results/combined
python -m marketlens.reporting --manifest results/latency/manifest.json --output /tmp/marketlens-final-replay
python -m streamlit run app/main.py --server.address 127.0.0.1 --server.port 8501
```

Commands used the checkout's `.venv/bin` executables. HTTP requests to the server's
health and root routes succeeded. AppTest exercised application logic, widgets,
charts and result generation; HTTP responses alone do not validate a complete UI.

## Issues found and resolved

- A penalty-only test incorrectly expected no opportunity cost on stochastic paths;
  its fixture now uses zero volatility to isolate the penalty, while separate tests
  verify the non-execution counterfactual.
- A chart and download widget shared a key, breaking rendered result pages. Keys
  are distinct and comparison/stress interaction tests verify the fix.
- A numeric-overflow test initially lacked its `replace` import; that test failure
  was corrected and the final full suite rerun successfully.
- Float overflow and invalid clocks/configurations now produce explicit errors
  instead of silent infinite output or future-state execution.
- Policy selection now controls which policies execute, and configuration changes
  invalidate saved comparisons rather than silently showing mismatched results.

## Limits of this evidence

No browser visual inspection, screenshots, macOS execution, user research, broker
connectivity, empirically calibrated model validation or fresh published-cloud-task
restoration was performed. Coverage is not proof of financial correctness. The
93-test suite, startup checks and saved experiment artifacts establish this
prototype's tested development workflow, not suitability for live trading.

## Version 0.2 product experience upgrade

The table above is the historical 0.1 record. The latest executed verification:

| Check | Actual outcome |
| --- | --- |
| Default/overview/comparison milestone before remaining view changes | 63 focused tests passed |
| Final full pytest with coverage | 111 passed; 0 failed; no skipped tests |
| Statement coverage | 1057 / 1068 statements; reported 99%, not branch coverage |
| Ruff lint and format, including scripts | Passed; 26 Python files formatted |
| pip check and editable 0.2.0 installation | Passed |
| All seven AppTest views and new interaction assertions | Passed |
| Desktop Chromium interaction and screenshots | Six actual screenshots captured; no browser page errors |
| HTTP health and root on the fresh verification server | Both HTTP 200 |
| Four new 100-seed studies | 8,400 actual trial-policy outcomes |
| Product trade-off export replay | All six output artifacts byte-identical |
| Legacy execution regression | Shared schema-1 execution columns preserved for tested matched seeds |

Browser evidence: `scripts/capture_screenshots.py` drives real Streamlit navigation,
runs the 10-seed preview comparison, opens exposure/penalty tabs and inspects the
waiting-policy decision view. Screenshots in `screenshots/` were captured at
1600×1150 with system Chromium; metadata is in `capture.json`. The overview,
comparison, simulation and decision screenshots were visually inspected. Initial
browser automation targeted a hidden radio input; selecting its visible label
resolved the automation failure. The original overview screenshot attempt was a
loading frame and is not used in the final evidence.

The first full upgrade run found one old UI-text assertion after the insights
wording changed; the assertion was updated to the new completion summary and the
full suite passed. Pandas join deprecation warnings were resolved using compatible
merge calls. Wilson endpoints now return exact 0/1 at the boundaries so chart
error lengths cannot become slightly negative through rounding.

Latest commands used the virtual environment:

```sh
python -m pytest --cov=marketlens --cov-report=term-missing -q
ruff check src tests app scripts
ruff format --check src tests app scripts
python scripts/capture_screenshots.py --base-url http://127.0.0.1:8502
python -m marketlens.reporting --suite tradeoffs --trials 100 --seed 42 --output results/product_tradeoffs
python -m marketlens.reporting --suite waiting --trials 100 --seed 42 --output results/waiting
python -m marketlens.reporting --suite urgency --trials 100 --seed 42 --output results/urgency
python -m marketlens.reporting --suite volatility_latency --trials 100 --seed 42 --output results/volatility_latency
python -m marketlens.reporting --manifest results/product_tradeoffs/manifest.json --output /tmp/marketlens-product-replay
```

Look-ahead and reproducibility: existing causal tests still pass; new tests show
that exposure and policy traces do not change when retrospective truth is changed,
that action markers use observed prices, that scenarios/policies reuse matched
paths, and that repeated new-suite runs reproduce exactly. No trading policy
receives diagnostics, truth overlays or the future fault schedule.

Remaining limits: no human usability study, accessibility certification, macOS
execution, empirical calibration, live trading or operational-safety validation.
The screenshots document a desktop research prototype, not those unperformed checks.
