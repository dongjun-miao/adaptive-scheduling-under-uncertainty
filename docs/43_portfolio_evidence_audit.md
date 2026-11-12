# Portfolio evidence audit

Source of truth:64 final Phase2C JSON files in phase2c-final-pilot, not preliminary runs or cached summaries. scripts/build_figures.py re-extracts numbers directly and writes figures/figure_data_manifest.json with input SHA256 for every run. Data extraction run twice produced identical manifest hash EEEBD6BADCDCEB23A73226A05FDCF081B85D497778208FA7BFA2610FB2F6381B. Presentation/layout changes do not change manifest data. No scheduling models or experimental outcomes changed.

|Claim|Source|Configuration / verification|Limitations|Public?|
|---|---|---|---|---|
|64 final runs, no failures|raw run status and ledger|64 files extracted; audit_phase2c rehydrated/validated/replayed|tiny plus one benchmark|Yes|
|B2-B1=-161/+159 stationary abz5|four relevant raw makespans|subtract paired outcomes, same manifest hash|two seeds, no inference|Yes|
|B3 fallback80.0%|every raw callback decision/fallback flag|672 starts /840 total; callbacks3846, episodes8, budget-exhaustion callbacks690|counts include deterministic duplicate seeds; not independent samples|Yes|
|B4-B2=-40/+125 stochastic slowdown|raw makespans|paired subtraction|calendar exposure endogenous|Yes|
|Plan/start B2 mismatch221/812|raw attribution records|source-plan vs callback estimates; raw audit checks links|planned coverage only, excludes28 fallback starts|Yes|
|Independent validation and replay|engine.py, residual.py, prediction_metrics.py; tests|130 tests plus raw audit successful|no proof of correctness beyond scope|Yes|
|EMA public-only arithmetic|forecasting.py|ratios from public completion, alpha1/4, exact ceiling|cooperative process boundary|Yes|
|Universal superior algorithm|none|unsupported|small pilot and confounding|No|
|HKU collaboration/publication acceptance|none|not present|independent application portfolio only|No|

Policy definitions checked against policies.py/triggers.py/forecasting.py. B0 release-time FIFO is earlier diagnostic, not final B1-B4 comparison. Nominal/EMA updates and trigger permissions share solver machinery. Final pilot settings: docs39, raw config/scenario and Result.parameters/response_proto; period/cooldown3/200, threshold1/4, deterministic effort .02/.20, safety10s, seed0 worker1. Exact Fraction engine and integer CP adapter boundary described. All pilot releases are0; arrival dynamics are unit tests, not an empirical arrival study.

References verified against official Google job-shop page, official NIST EWMA section and pinned benchmark README/LICENSE. No invented authors, DOI, publication venue or supervisor. Sources linked in README. Factual numeric evidence is internal original data; citations do not substitute for it.

License: upstream root MIT notice inspected and copied verbatim to licenses/TUE_MIT.txt. Small fixtures/abz5 attribution retained. No separate data-specific grant was found during this audit; public redistribution should receive final human review. New blanket license for original code deliberately not invented.
