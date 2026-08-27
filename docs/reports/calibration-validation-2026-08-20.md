# Calibration and virgin-seed validation — closing the cold-start gap (2026-08-20)

One parameter moved — `escalation_min_samples` 8 → 9 — and it moved with the full
out-of-sample discipline: diagnosed on the gate sweep, located by 1-D sensitivity on
disjoint seeds, confirmed by the 2-D interaction slab, and validated on forty virgin
seeds no analysis had ever touched. All offline, deterministic, scripted doubles:
135 slab runs in 744 s plus 16,800 validation student-days in 343 s, $0, thermally
capped at 2–3 workers under `nice`.

## Seed hygiene

| Seed range | Used for | Status |
|---|---|---|
| 20260901 | threshold/simulator calibration | in-sample, excluded everywhere |
| 20260902–41 | pre-registered gate sweep | spent on gating |
| 20260950–64 | sensitivity curves + 2-D slab | spent on choosing the value |
| 20261000–39 | **this validation** | virgin until this run |

## The 2-D slab (min_samples × STRUGGLING_CEILING, 15 seeds/cell)

| min_samples | ceiling 0.35 | ceiling 0.40 | ceiling 0.45 |
|---|---|---|---|
| 8 | 0.918 / 0.993 | 0.906 / 1.000 | 0.877 / 1.000 |
| **9** | 0.978 / 0.993 | **0.964 / 1.000** | 0.938 / 1.000 |
| 10 | 0.985 / 0.985 | 0.971 / 1.000 | 0.964 / 0.965* |

(precision / recall; * = recall cost appears) — no interaction overturns the 1-D
reading. Decision: **9 at ceiling 0.40** — the minimal move inside the plateau with
recall 1.000 and first-detection latency still ≈ day 3.

## Virgin-seed validation vs the pre-registered gates

| Gate | Bar | Original | +G7 fix | +min_samples 9 (virgin) | Verdict |
|---|---|---|---|---|---|
| G1 recall complete | ≥ 95 % | 36/40 | 38/40 | 38/40 | **passes** |
| G2 zero FP students | ≥ 95 % | 16/40 | 19/40 | 30/40 | **still fails** |
| G3 cooldown gaps | 100 % | 40/40 | 40/40 | 40/40 | passes |
| G4 engagement | ≥ 90 % | 36/40 | 35/40 | 36/40 | passes |
| G5 cohort clean | ≥ 95 % | 29/40 | 30/40 | 38/40 | **passes** |
| G6 injections | 100 % | 40/40 | 40/40 | 40/40 | passes |
| G7 hedged strict | 100 % | 36/40 | 40/40 | 40/40 | passes |
| G8 fast-guess | ≥ 90 % | 40/40 | 40/40 | 40/40 | passes |

Pooled struggle metrics, same progression: precision 0.892 → 0.918 → **0.970
[0.947–0.983]**; recall 0.989 → 0.994 → **0.994 [0.980–0.998]**; interrupts per 420
student-days p50 52 → 53, p95 71 → 63. Baselines unchanged: never-interrupt recall 0,
rate-matched random precision 0.300.

## Honest read

1. **G2 still fails its own bar.** Eleven FP students remain across 40 virgin seeds.
   Whether they are residual cold-start or a second mechanism is unknown until they get
   the same ground-truth scoring the first 32 received. The gate stays red on the board.
2. The precision gain costs first-detection latency: one more attempt of evidence
   (~day 3). The slab shows 10 would pay more latency for +0.007 — not taken.
3. Same simulator caveat as every offline number: plateaus this clean live in a
   simulator with a bimodal ability gap; a classroom is a continuum. The pilot and the
   live calibration remain the only external checks.

## Artifacts

`.local_data/validation/results.json` (40 rows) · slab console table (this report).
