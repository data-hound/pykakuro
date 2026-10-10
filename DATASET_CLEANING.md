# Kakuro dataset cleaning: strategies and algorithms (v2 built for 9×9, 11×11 and 15×15)

Status date: 2026-10-09. Scripts live in `analysis/`; every number below is reproducible from them. Raw
outputs are in `analysis/out/`. The v2 data is at `ar-diffusion-2d/data/kakuro_kraze_v2/grid{9,11,15}/{train,validation,test}.parquet`; `analysis/run_size.sh <size>` reruns the whole pipeline for one size.
**Nothing has been uploaded to HF or pushed to GitHub.** The old `kakuro_kraze/` data is untouched.

## 1. Problem being fixed
`generate_dataset.py` writes a row for every seed even when `solve()` hit its 5 s wall-clock timeout, and sets
`is_exclusive = puzzle.is_exclusive and len(puzzle.solutions) <= 1`. After a timeout `solutions` is empty or partial,
so the flag is True without uniqueness ever being established. `clean_kakuro_dataset_for_hf.py` filtered only on that flag.
Independent check (CP-SAT) on the raw 11×11 pool: of the 143 220 puzzles the generator flagged exclusive,
**23 189 (16.2 %) have ≥ 2 solutions**, all with the timeout signature; the generator was right about the other 194 119 + 12 661 it rejected.
The paper's "verified unique" claim therefore did not hold for 15.7 % of released 11×11 puzzles.

## 2. Pipeline for one grid size (11×11 as run)

| Stage | Script | What it does | 11×11 result |
|---|---|---|---|
| 0 Pool provenance | `05_verify_pool.py` (header) | Load all raw parts `kakuro_mania/board_11_part_*.parquet`; check seed and puzzle-string uniqueness | 350 000 rows, 350 000 unique seeds, 350 000 unique strings |
| 1 Structural validity + independent uniqueness | `03_verify_uniqueness.py` (`work`), `05_verify_pool.py` | For **every** pooled puzzle: parse, derive runs, validate the stored solution, count solutions up to 2 with CP-SAT | 0 errors, 0 structural problems, stored solution valid in 100 % |
| 2 Keep only independently unique | `06_pool_summary.py` | Keep `status == unique` and stored solution == the solver's solution | **120 031** unique (34.3 %) |
| 3 Canonical duplicates | `07_canonical_dups.py` | Crop + transpose canonical hash | 0 duplicate groups |
| 4 Near-duplicates | `07_canonical_dups.py` | MinHash-LSH + exact Hamming verification | 0 pairs (≤ 12 of ~121 cells) |
| 5 Re-split (minimal-change repair) | `08_build_v2_grid.py` | See §4 | 50 000 / 5 000 / 5 000 |
| 6 Post-hoc end-to-end re-verification | `03_verify_uniqueness.py --data …_v2/` | Re-run the solver on the *written* files | 60 000 / 60 000 unique, stored == found |
| 7 Component overlap report | `08_build_v2_grid.py` | See §5 | `out/grid11_v2_report.json` |

## 3. Algorithms

### 3.1 Parsing and run derivation
Cell codes: `0` black, `1` white, `(right, down)` clue cell. For each clue cell with `right > 0`, the run is the maximal sequence of white
cells to its right; likewise downward for `down > 0`. A run with no cells, or a white cell in no run, is a structural problem
(none found). This is separate code from `kakuro.py` (nothing from the generator is reused).

### 3.2 Stored-solution check
Every white cell has an integer 1–9; each run has distinct digits summing to its clue.

### 3.3 Uniqueness (solution counting to 2)
CP-SAT model: one integer variable in [1, 9] per white cell, `AllDifferent` per run, `sum == clue` per run. Enumerate solutions
(`enumerate_all_solutions`, one worker) with a callback that stops after two. Outcome: `multiple` (two found), `unique`
(search exhausted with exactly one), `none` (infeasible), `limit` (resource limit, undecided). The limit is a *deterministic* time
(20 units) with a wall-clock safety net, so outcomes do not depend on machine load (the original generator's wall-clock timeout did).
Puzzles with `limit` or `none` would be excluded and counted; there were none. A puzzle is accepted only if `unique` **and** the
solver's solution equals the stored one.

### 3.4 Canonical form and exact duplicates
Tokens per cell: black, white, or `(C, right, down)`. Crop to the bounding box of non-black cells (removes dead border rows/columns,
so shifted copies collide). Form two grids: the cropped grid and its transpose with each clue pair swapped; the canonical form is the
lexicographically smaller `repr`; the hash is xxh64 of it. Flips/rotations are not applied because they change the reading direction
of runs and are not semantics-preserving.

### 3.5 Near-duplicates
Each canonical grid is the set `{(row, col, token)}`. MinHash (128 permutations) with LSH threshold ≈ 0.9 × the Jaccard value implied by a
Hamming distance of 10 % of cells proposes candidates; each candidate is verified by exact Hamming distance on the cell tokens, requiring
the same crop shape. Limits: LSH is probabilistic (recall < 100 %), and puzzles with different crop shapes are not compared. 0 pairs
means "none found at this recall", not a proof of absence.

### 3.6 Re-split (minimal-change repair)
Goal: fix validity without discarding the evaluation history. For each split `s`: keep every old puzzle that is independently unique,
then top up to the original size with puzzles drawn uniformly (seed 42) from verified-unique puzzles that appeared in **no** old split.
Test is filled first. Resulting v2 counts:

| Split | old size | kept (unique) | removed (not unique) | topped up |
|---|---|---|---|---|
| test | 5 000 | 4 213 | 787 | 787 |
| validation | 5 000 | 4 148 | 852 | 852 |
| train | 50 000 | 41 926 | 8 074 | 8 074 |

Consequences and caveats:
- **Comparability.** 4 213 of 5 000 v2 test puzzles are identical to old test puzzles, so a model's old score can be re-scored on exactly that kept subset (column `legacy_split`/`topped_up` identifies it). The 787 new test puzzles are fresh.
- **Models trained on the old train split** saw the 8 074 removed (non-unique) puzzles; retraining is not needed for validity of the *test*, but is cleaner.
- **`puzzle_id`** is xxh64 of the solution string, as before; 0 mismatches with legacy ids for kept rows.
- Seed-based reproducibility holds: v2 rows carry `seed` and the raw pool is unchanged.
- **Distribution shift.** Unique-only puzzles are not a random sample of generator output (non-unique puzzles were removed). This is intended; it should be stated in the paper.
- No new puzzles needed generating for 11×11: the verified-unique pool (120 031) exceeds the 60 000 needed. For 15×15 the unique yield of the 350 k pool is **not yet known** (only 44 % of the *released* 15×15 puzzles are unique, and the released set was already filtered by the flag; by analogy with 11×11, where the pool yield was 34 %, 15×15 may yield well under 60 000 per ~350 k). Run `05_verify_pool.py --size 15` to find out; if it falls short, regenerate with the fixed generator (§6) using new seed ranges.

### 3.7 Decontamination rules (enforced as assertions)
Fail the build if: any puzzle string, solution string or canonical hash is shared between splits or repeated within a split;
a train row is a canonical duplicate or near-duplicate of a val/test row. None triggered for 11×11. (If one triggers, the rule is: drop from
train, never from val/test, and refill.)

## 3.8 Results for all three sizes (every number from `analysis/out/*report.json`, `pool*_summary.txt`)

| | 9×9 | 11×11 | 15×15 |
|---|---|---|---|
| raw pool (seeds 0–349 999) | 350 000 | 350 000 | 350 000 |
| independently unique in pool | 178 585 (51.0 %) | 120 031 (34.3 %) | 47 460 (13.6 %) |
| generator flag True but NOT unique | 9 819 | 23 189 | 62 329 |
| newly generated (seeds 350 000–549 999, same generator, CP-SAT gate) | – | – | 27 460 unique of 200 000 seeds (13.7 %) |
| verified-unique candidates used | 178 585 | 120 031 | 74 920 |
| canonical duplicate groups / near-dup pairs | 0 / 0 | 0 / 0 | 0 / 0 |
| v2 test: kept legacy / new | 4 756 / 244 | 4 213 / 787 | 2 217 / 2 783 |
| v2 val: kept legacy / new | 4 743 / 257 | 4 148 / 852 | 2 128 / 2 872 |
| v2 train: kept legacy / new | 47 445 / 2 555 | 41 926 / 8 074 | 21 621 / 28 379 |
| re-verification of written v2 files | 60 000 / 60 000 unique | 60 000 / 60 000 unique | 60 000 / 60 000 unique |
| test component overlap (mean share of white cells in train components) | 54.5 % | 53.2 % | 52.6 % |

15×15 caveat: only 44 % of the legacy 15×15 test set survives, so v2 test is 56 % new puzzles (seeds ≥ 350 000 or never-released pool seeds); old 15×15 scores can be re-scored only on the 2 217 kept puzzles. 15×15 generation (`09_generate_unique.py`) reuses the unchanged `gen_random` and `kakuro.print_lol` and uses CP-SAT as the acceptance gate, so the old solver's slow, timeout-prone enumeration is bypassed (about 5 ms per seed); the legacy `difficulty` field was then computed for accepted puzzles with a 30 s old-solver timeout (NaN if it times out).

## 3.9 Near-duplicate assurance: what was done, and what it does and does not show

**Layers (all run on the v2 splits or the pool they were drawn from; 0 duplicates found at every layer):**
1. *Exact string overlap* between splits (`02_exact_split_overlap.py`): 0 for all sizes.
2. *Canonical duplicates* (crop to non-black bounding box + transpose with clue swap, xxh64) over the whole verified-unique pool (`07_canonical_dups.py`): 0 duplicate groups at every size, so none within or across splits.
3. *Approximate near-duplicate search* (MinHash-LSH on the set of (row, col, cell token), 128 permutations, candidates verified by exact Hamming distance, threshold 10 % of cells, same crop shape) over the same pool: 0 pairs. This layer is probabilistic (recall below 100 % near the threshold) and skips pairs with different crop shapes.
4. *Exact nearest-neighbour audit* (`21_exact_nn_audit.py`, added 2026-10-09 to remove the probabilistic caveat): for every validation and test puzzle, a brute-force comparison against **all** 50 000 training puzzles (and test↔validation, and within-split), minimum over both orientations (as is, and transposed with clue pair swapped). Distance = number of cells whose token (black / white / clue with its right and down sums) differs. No hashing and no sampling in the held-out→train comparison.
5. *Component-level overlap* (section 5): small components recur, components of 6+ cells essentially never.

**9×9 (81 cells)**

| pair | n | closest pair: differing cells | 1st percentile | median | pairs within 20 % |
|---|---|---|---|---|---|
| test->train | 5,000 | 29 (35.8 %) | 42.0 % | 50.6 % | 0 |
| validation->train | 5,000 | 30 (37.0 %) | 43.2 % | 50.6 % | 0 |
| test->validation | 5,000 | 29 (35.8 %) | 45.7 % | 53.1 % | 0 |
| test->test(self excl.) | 5,000 | 32 (39.5 %) | 45.7 % | 53.1 % | 0 |
| null: train(sample)->train(self excl.) | 3,000 | 30 (37.0 %) | 43.2 % | 50.6 % | 0 |

Kolmogorov–Smirnov, test→train vs train→train null: p = 0.69

**11×11 (121 cells)**

| pair | n | closest pair: differing cells | 1st percentile | median | pairs within 20 % |
|---|---|---|---|---|---|
| test->train | 5,000 | 56 (46.3 %) | 50.4 % | 56.2 % | 0 |
| validation->train | 5,000 | 56 (46.3 %) | 50.4 % | 56.2 % | 0 |
| test->validation | 5,000 | 60 (49.6 %) | 52.9 % | 58.7 % | 0 |
| test->test(self excl.) | 5,000 | 55 (45.5 %) | 52.9 % | 58.7 % | 0 |
| null: train(sample)->train(self excl.) | 3,000 | 57 (47.1 %) | 50.4 % | 56.2 % | 0 |

Kolmogorov–Smirnov, test→train vs train→train null: p = 0.44

**15×15 (225 cells)**

| pair | n | closest pair: differing cells | 1st percentile | median | pairs within 20 % |
|---|---|---|---|---|---|
| test->train | 5,000 | 127 (56.4 %) | 59.1 % | 62.7 % | 0 |
| validation->train | 5,000 | 126 (56.0 %) | 59.1 % | 62.7 % | 0 |
| test->validation | 5,000 | 133 (59.1 %) | 60.9 % | 64.4 % | 0 |
| test->test(self excl.) | 5,000 | 128 (56.9 %) | 60.9 % | 64.4 % | 0 |
| null: train(sample)->train(self excl.) | 3,000 | 129 (57.3 %) | 59.1 % | 62.7 % | 0 |

Kolmogorov–Smirnov, test→train vs train→train null: p = 0.36

**Reading.** No held-out puzzle has a training neighbour closer than 36 % (9×9), 46 % (11×11) or 56 % (15×15) of cells, i.e. there is no near-duplicate at *any* threshold up to about a third of the board; the 10 % rule used by the build is far from binding. The nearest-neighbour distance distribution of test→train is statistically indistinguishable from the train→train null at every size (KS p = 0.44 / 0.69 / 0.36 for 11 / 9 / 15), i.e. held-out puzzles are no closer to training puzzles than training puzzles are to each other, as expected for independent draws. The same holds between validation and test and within each split, so the effective sample size of the held-out sets is not reduced by near-duplicates.

**What this does not cover.** (a) Similarity of *parts* of boards: handled by the component overlap analysis, not by whole-board distance; 3–5-cell components recur by necessity. (b) Shifted copies: boards are compared at their fixed top-left anchoring (the generator always makes the first row and column black / clue), and the canonical-hash and component analyses are translation-invariant. (c) Memorisation by pretraining: the data was private until 2026-10-09 and cannot be checked against model pretraining corpora.

**Enforcement.** `21_exact_nn_audit.py --gate_frac 0.10` exits non-zero if any validation or test puzzle is within the given fraction of cells of a training puzzle (or test↔validation); run it before any future release. `08_build_v2_grid.py` additionally asserts no canonical duplicate and no LSH pair touching held-out data. Any future regeneration must pass both and the row/column-distinct-digit gate (`kk_property.py`).

## 4. Residual issues found but deliberately not changed
- **Length-1 runs** are ~66 % of runs on average: many cells are fixed directly by a single-cell clue. They are part of the generator's distribution; we document rather than filter (filtering would change the task). Report cell accuracy alongside grid accuracy and stratify.
- **Stored `difficulty`** was timeout-capped (legacy rows) or wall-clock dependent (new 15×15 rows). v2 **removes it** (the v1 files keep it) and ships a deterministic replacement, fully documented in `DIFFICULTY_METRIC.md`: (`11_solver_difficulty.py`, `12_merge_and_compare.py`): `solver_prop_fixed_frac` (share of white cells fixed by propagation alone), `solver_search_nodes` (MRV backtracking nodes to exhaust the tree, cap 200 000, never reached), `difficulty_score` (mean of the two percentile ranks) and `difficulty_tertile` (0–2 within size, ~20 000 each). Spread: median nodes 3 / 5 / 12 and root-solved share 19.6 % / 6.7 % / 0.4 % for 9 / 11 / 15.
- `is_exclusive` in v2 is `True` for every row and is now backed by `verified_unique` (independent CP-SAT), not by the generator.

## 4b. Extra verification layers on all 180 000 v2 rows
1. CP-SAT enumeration to 2 solutions (`03`), 2. a separate own propagation + backtracking solver (`11`; status unique and solution equals stored for 100 %), 3. CP-SAT block-and-resolve (forbid the stored solution, require infeasible; 100 % infeasible). The 27 460 newly generated 15×15 puzzles therefore have the same three layers as legacy ones.

## 4c. Distribution checks (`out/v2_distribution_report.json`)
- Topped-up vs legacy-kept test puzzles are indistinguishable on n_white, n_runs, length-1-run share, propagation share and search nodes (two-sample KS p ≥ 0.2 for every feature at all three sizes); 15×15 old-seed vs new-seed train puzzles likewise (p ≥ 0.56). So re-scoring old results on the legacy-kept subset is comparable to the new puzzles.
- v1 vs v2 test **does differ** (KS p < 0.05 for white cells and length-1 share at 9×9; p ≈ 1e-17…1e-275 at 11×11 and 15×15): unique-only boards are smaller (15×15 mean white cells 76.1 → 72.4) with more length-1 runs (63.6 % → 68.1 %). This is a real selection effect of the uniqueness requirement and must be stated.

## 4d. Generator artifact: digits are distinct across whole rows and columns (not just runs)
`pykakuro.gen_random` places a digit only if it appears nowhere in the cell's row and column. Consequently **100 % of released solutions (train and test, all three sizes; `analysis/17_global_distinct_check.py`) have row-wide and column-wide distinct digits**, a property real Kakuro does not require (it only requires distinctness inside a run). A model trained or evaluated only on this data may exploit it. This is a genuine property of the benchmark and is stated in the dataset card.

**KK-Shift (shifted-generator sets, `analysis/18_generate_shift.py`) — HELD, NOT USED (2026-10-09 instruction: the row/column-distinct-digit property must be preserved for all analysis; these sets lack it by design):** same layout process and clue computation, but digits are distinct only inside runs, so they may repeat across runs of one row/column. Every puzzle is CP-SAT-unique (plus the own-solver and block-and-resolve checks) and carries the same solver-difficulty columns (tertile cut points taken from the v2 pool). Variants: `nodistinct` (same white-cell probability 0.40; mean white cells 24.2 / 37.8 / 74.0 for 9 / 11 / 15, versus 24.2 / 37.6 / 72.4 in v2, so density is matched and only the artifact is removed) and `dense` (probability 0.50; 29.6 / 46.1 / 90.7). Acceptance rate (unique / generated): nodistinct 51.1 % / 34.8 % / 11.1 %; dense 24.1 % / 10.0 % / 1.1 %. Output: `ar-diffusion-2d/data/kakuro_shift/{variant}_grid{N}.parquet` (1 500 each) and the balanced evaluation set `kakuro-craze/benchmark/kk_shift_v1.parquet` (100 per size × tertile × variant, 1 742 puzzles; the dense 15×15 easy tertile has only 42).

## 4e. Uniqueness under the stricter (row/column-distinct) rule: v2 is valid under both definitions
The original solver, my CP-SAT check and the task prompt all use the standard rules (distinct digits **within each run**). The dataset additionally has the row/column-wide property (section 4d). If that property is imposed as a rule, a puzzle with several run-level solutions can have a single one (`analysis/20_global_rule_uniqueness.py`, v1 test sets, 5 000 puzzles per size):

| size | run-level unique (kept in v2) | run-level NOT unique | of those, unique under the stricter rule | still several solutions |
|---|---|---|---|---|
| 9×9 | 4 756 (all still unique) | 244 | 45 (18.4 %) | 199 |
| 11×11 | 4 213 (all still unique) | 787 | 384 (48.8 %) | 403 |
| 15×15 | 2 217 (all still unique) | 2 783 | 2 013 (72.3 %) | 770 |

Consequences: (a) every v2 puzzle is unique under **both** definitions (a run-level-unique puzzle stays unique when more constraints are added), so v2 is correct whichever definition is adopted. (b) Under the stricter definition, 2 442 of the 3 814 removed v1 test puzzles (across the three sizes) would also have been valid, so v2 is the conservative choice; it biases toward puzzles whose uniqueness does not depend on the extra property. (c) The task prompt does not state the extra rule, so a model cannot be expected to use it; scoring against a puzzle that is unique only under the stricter rule would mark valid-by-prompt answers wrong. A future "v2.1" could add stricter-rule-unique puzzles, but only together with a prompt that states the row/column rule (a prompt-sensitivity variant worth running regardless). The claim in the paper should name the definition used: "unique under the standard run-level rules" for v2.

## 5. Component-level overlap (memorisation exposure), 11×11 v2
Connected white components (4-neighbour) are keyed by relative cell positions plus the governing clue sums, translation- and transpose-invariant.
Fraction of held-out white cells lying in components that also occur in train:

| Component size (cells) | test | validation |
|---|---|---|
| 1 | 100 % | 100 % |
| 2 | 100 % | 100 % |
| 3–5 | 65.4 % | 65.3 % |
| 6–10 | 0.04 % | 0 % |
| ≥ 11 | 0 % | 0 % |

Per-puzzle mean 53 %, p90 78–79 %. Reading: components of ≤ 2 cells recur necessarily (there are only a handful of possible 1- and 2-cell patterns); medium components (3–5) partly recur; components of ≥ 6 cells essentially never do. Whole-board overlap is nil, but small-pattern memorisation cannot be excluded by splitting alone. This is a property of the generator, not removable by dedup, and should be disclosed.

## 6. Generator fixes (applied 2026-10-10 in `src/pykakuro/`; the v2 data does not depend on them)
1. `generate_dataset.py` records `solve_finished`; `is_exclusive` is True only if the solve finished (rows of timed-out solves are kept but flagged, so the pool keeps its structure).
2. The wall-clock timeout is kept only as a budget; it no longer decides anything: acceptance is the independent CP-SAT gate (`analysis/03_verify_uniqueness.py`, `analysis/09_generate_unique.py`). A node budget in the legacy solver was not implemented.
3. Failures are counted correctly (`f()` used to return the exception *class*, so `isinstance(err, Exception)` was False and logged failure rates were too low); timeouts are counted separately.
4. Rows where `check_solution` raised are kept but flagged (`solution_check_ok=False`, `is_exclusive=False`) instead of being treated as fine. They are not dropped: in a 60-seed 9×9 smoke test 22 raised "Unfilled entries" on the solver's output although the stored master solutions are valid under the independent check, so dropping would silently change the yield.
5. `gen_random` uses a local `random.Random(seed)` and `seed is not None` (seed 0 used to be unseeded; the global RNG was reseeded as a side effect). Regression check: 900 boards (300 per size, seeds ≥ 1) regenerated from the raw pool are identical to the stored puzzle and solution strings; the global RNG state is untouched; seed 0 is deterministic.
6. The independent post-generation CP-SAT uniqueness gate is the acceptance test of `analysis/09_generate_unique.py`.
Not changed on purpose: the digit placement rule (row/column-distinct), because the study depends on that property (section 4d).

## 7. Release status
*Updated 2026-10-10; the first version of this section (written before the upload) said the HF repo was public with the old data and that v2 and the difficulty strata were still to do. Both are done.*
- **HF** `Apaxdor/kakuro_kraze`: the owner uploaded v2 on 2026-10-09 (commit `1c677bdc`; tag `v1` = the old release, sha 2531b9b, which is byte-identical to the local `kakuro_kraze/` per `analysis/10_compare_hf_to_local.py`; tag `v2` = this release) and then set the repo **private**. The 9 uploaded parquet files are byte-identical to the staged copy `ar-diffusion-2d/data/hf_staging_v2/`, which passed the row/column-distinct gate (180 000 rows). The `seed` column is deliberately not exposed.
- **Not done, needs the owner (write token and go-ahead)**: (a) push the updated card, which adds the "Generator artifact" bullet: `python -I analysis/14_upload_to_hf.py --readme_only --retag_v2 --go`; (b) decide when to make the repo public again (the v1 data is invalid for scoring against a single stored solution, KNOWN_CAVEATS B1; v2 is the release to point reviewers at).
- **Card contents**: independent CP-SAT verification, minimal-change repair policy, unique-only distribution shift, length-1-run share, §5 overlap table, which test puzzles are legacy vs new (`legacy_split`, `topped_up` columns), and the solver-based difficulty columns (`DIFFICULTY_METRIC.md`).
- **Generator and cleaning code:** the local `pykakuro` working tree now contains the §6 fixes, the cleaning pipeline and a README describing them (updated 2026-10-10). It is **not pushed**; until the owner pushes it, the public GitHub repo (`data-hound/pykakuro`) still lacks them (KNOWN_CAVEATS B5). The difficulty strata (Stage F) are done.
