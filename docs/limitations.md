# Limitations and scope

- Entirely synthetic, uncalibrated data; no evidence of real-world profitability,
  execution safety, commercial demand or applicability to a particular firm.
- GBM has continuous lognormal dynamics with constant drift/volatility. It omits
  jumps, clustering, intraday seasonality, autocorrelated order flow and changing
  spreads/liquidity. Presets are fixed parameter changes, not regime switching.
- At second-scale horizons annualised GBM moves can be tiny. This is correct unit
  conversion, not evidence that latency is harmless. Some default scenarios will
  have identical decisions and outcomes by construction. Longer horizons, higher
  volatility or different thresholds are sensitivity choices, not calibrated facts.
- Fixed latency and independent loss omit jitter, packet reordering, duplicated
  quotes, clock skew, correlated faults and burst recovery. Outage suppression is
  defined by delivery time, while stale windows use source time.
- Constant displayed liquidity is not a matching engine. All-or-none fills and
  the linear impact coefficient are illustrative; no partial fills, depth,
  replenishment, queue priority, spread crossing dynamics or competing orders.
- Only one buy order per path. No portfolio accounting, sell orders, adverse
  selection model, strategy alpha or real-money connection.
- Discrete decision grids and threshold boundaries affect waiting. Sensitivity
  should include time resolution as well as policy thresholds.
- Non-execution opportunity cost and penalties are assumptions. A policy that
  avoids fills can look cheap under a weak penalty. Always show completion.
- Filled-cost distributions can represent different subsets across policies.
  Paired adjusted costs depend on the penalty. Small-sample intervals and tail
  estimates are uncertain; sweeps have no multiplicity correction.
- Policies are trusted Python code with a restricted input contract, not sandboxed
  plugins. API isolation prevents accidental look-ahead; it is not a security boundary.
- Editable source checkout is the supported dashboard workflow. The CLI and core
  package install normally; documentation displayed by the app lives in `docs/`.
- The upgrade includes actual Chromium screenshots and desktop visual inspection.
  Automated UI/browser tests and HTTP checks do not constitute human usability
  research, accessibility certification, or macOS verification. Screenshot previews
  use 10 seeds; repeated-trial findings use 100 and can have different conclusions.

Before operational use: obtain licensed real data, calibrate models, model venue
rules and clocks, independently validate risk controls, test realistic network
faults, implement monitoring/security and obtain appropriate professional review.
