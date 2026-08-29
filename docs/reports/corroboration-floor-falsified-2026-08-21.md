# The corroboration floor, falsified on its own terms (2026-08-21)

**The proposed guard is dead, killed by the protocol its proposer pre-declared.** The
corroboration floor (escalate only when the recency EMA *and* the cumulative accuracy
both sit under the struggling ceiling) promised to cut the G2 residue by two thirds.
Its falsification protocol — written into `fp-residue-2026-08-21.md` before any run,
with fresh seeds and three joint acceptance criteria — was executed exactly as
declared. Two of three failed. The change was reverted the same hour. All offline,
deterministic: 40 gate seeds + 20 school-week seeds (20261300–20261339, now spent),
253 s + ~340 s, $0, 3 workers under `nice`.

## Verdict against the pre-declared criteria

| Criterion | Bar | Measured | Verdict |
|---|---|---|---|
| G2 zero-FP seeds | ≥ 38/40 | 35/40 | **fail** |
| School-week struggle recall | ≥ 0.95 | 0.900 [0.847–0.936] | **fail** |
| Median school-week detection latency | ≤ 6 scheduled days | 4 | pass |

## What actually happened

The floor bought precision at recall's expense: gate-sweep precision rose to 0.982
[0.962–0.992] but recall fell 0.994 → **0.917 [0.884–0.941]**, and ledger-complete
recall collapsed to 16/40 seeds. Under the school calendar, 18 of 180 struggling
students were never detected within 42 days. The proposal's own cost model predicted
this failure mode in advance: "a deferral inside a closing window can cost recall
outright." It did.

## What stands after the revert

The shipped configuration remains the one validated on 2026-08-20: precision 0.970
[0.947–0.983], recall 0.994 [0.980–0.998] on virgin seeds, 7/8 pre-registered gates.
The G2 residue (11 FP students / 40 seeds) keeps its root cause on the record: the
EMA is seeded from the first outcome and three consecutive misses reach the
struggling band from any prior history. Threshold-level guards are now exhausted —
two swept, one slab-confirmed, one falsified. **The remaining fix is the estimator
itself** (slip/guess separation — the BKT shadow-model block in
`docs/product/self-learning.md`), which is product work, not calibration.

## Honest read

1. This is the system working as designed: pre-registered criteria made the negative
   result cheap, fast and undeniable — the guard lived four hours from proposal to
   grave, and nothing about the decision was discretionary.
2. Cost asymmetry decided it. A missed struggling child outweighs a spurious parent
   ping; any guard that trades recall for precision starts from a deficit.
3. Seeds 20261300–20261339 are spent and recorded here for the hygiene table.
