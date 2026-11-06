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
