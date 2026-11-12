# Adaptive Scheduling under Uncertain Processing Times: A Reproducible Empirical Study

## Research motivation

How do forecast updates and replanning triggers affect realized job-shop scheduling under controlled information and optimization budgets? Improving a forecast need not improve the resulting execution.

## Technical approach

Independent Python discrete-event simulator with exact Fraction timing; private scenario/public observation boundary; residual OR-Tools CP-SAT with frozen running work; safe plan commitment and dispatch; fixed nominal and machine-level EMA forecasts (alpha 0.25); periodic, event and forecast-threshold triggers.

## Controlled pilot

64 final runs: tiny diagnostic plus public abz5, four duration regimes, seeds 11/29, one optimizer repetition. Paired policies use identical exogenous manifests and configured effort caps. Recorded start-time and authorizing-plan-time predictions are evaluated separately; fallback coverage is explicit.

## Evidence-based findings

Stationary abz5 EMA-periodic versus nominal-periodic changes makespan by -161 and +159 across the two seeds. Event-triggered B3 starts 80.0% of operations through fallback after budget pressure; its outcomes cannot be treated as pure trigger effects. Threshold triggering has favorable and unfavorable cases. No general superiority or statistical significance claim is made.

## Research skills demonstrated

Python engineering; nonpreemptive scheduling and CP-SAT modeling; discrete-event simulation; online calibration; experimental controls; adversarial tests; independent metric reconstruction; solver-status, budget and provenance accounting; scientific communication.

## Repository and reproducibility

130 regression tests pass. Final raw scenarios, execution ledgers, solver responses, plan forecasts and reproducible figures are supplied. README contains tested smoke, audit and plotting commands. Source-only portfolio is prepared for review; no public repository URL or publication is claimed.

## Scope and next step

Independent research portfolio for AI + Operations Research RA applications, including HKU. No HKU affiliation or supervision is implied. Main limits: one public instance, few seeds, fallback confounding, policy-dependent prediction exposure and platform-sensitive reoptimization. Next: externally reviewed preregistration for a broader study.