# Product experience upgrade plan

This increment extends the existing system; it does not replace its simulation,
policy or execution semantics. Policies remain observation-only.

1. **Default and decision intelligence.** Add an explicitly synthetic reliability
   stress demonstration, a separate healthy baseline, and pure retrospective
   insight functions. Extend trial records with observable quote age at submission,
   stale/no-quote execution flags and time-weighted stale exposure while pending.
   Update overview and comparisons with explanations, uncertainty and friendly tables.
   Test these changes before touching the remaining views.
2. **Visual explanation.** Add distinct truth/observed styles, reliability states,
   fault indicators and hoverable action markers to simulation and decision views.
   Replace raw JSON with useful observation/outcome summaries while preserving exports.
3. **Trade-off experiments.** Keep historical rule-validation sweeps; add matched
   urgency/freshness, waiting, volatility/latency, liquidity and deadline scenarios.
   Record favorable and unfavorable outcomes, paired costs on jointly filled orders,
   completion and penalty sensitivity without choosing actions using truth.
4. **Portfolio evidence.** Run repeated experiments and replay; capture actual browser
   screenshots if browser execution works; update README, methodology, strategy and
   verification. Run full pytest, Ruff, browser interactions and HTTP startup checks.

Affected modules: dashboard, a new presentation/insight boundary, scenario presets,
experiments, metrics, reporting, visualization helpers, tests and documentation.
The market generator, causal observation cursor and policy input contract remain
stable. Diagnostics from truth/fault schedules are always retrospective.

Acceptance: healthy ties are explained; the demo exposes different actions without
promising a winner; costs and completion are paired with uncertainty; no stale run
is labelled current; all seven views and existing exports remain usable.

## Completed verification

The default/overview/comparison increment passed 63 focused tests before the other
views were changed. Final verification passed 111 tests, Ruff lint/format checks,
HTTP startup checks and actual browser interaction/capture. Four new 100-seed
studies produced 8,400 outcomes. See `verification.md`, `experiments.md` and the
six actual screenshots for evidence; no policy superiority or user study is claimed.
