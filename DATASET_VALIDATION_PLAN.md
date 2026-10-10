# Plan 1 — Dataset validation (highest priority) — RE-SCOPED 2026-10-09: execution complete, release pending

**Status by stage** (details and numbers: `DATASET_CLEANING.md`, `DIFFICULTY_METRIC.md`, `analysis/out/`):

| Stage | State |
|---|---|
| A canonical copy / HF comparison | Done. HF `Apaxdor/kakuro_kraze` is public and identical to local v1 (`10_compare_hf_to_local.py`). |
| B independent validity + uniqueness | Done on the whole raw pool (3 × 350 000) and on all v2 rows. Result: v1 contained non-unique puzzles (4.9 / 15.7 / 55.7 % of test). |
| C canonical duplicates | Done: 0 groups (all sizes, within and across splits). |
| D near-duplicates | Done: 0 pairs at ≤ 10 % cell Hamming (MinHash-LSH, probabilistic recall). |
| E component overlap | Done, reported in `DATASET_CLEANING.md` §5. |
| F difficulty strata | Done, deterministic solver metric (`DIFFICULTY_METRIC.md`); old generator field removed. |
| G fixes | **Data fixed (v2 built, re-verified, staged).** Generator-code fixes (§G below) are documented but not applied. |
| Release | **Uploaded 2026-10-09 by the owner** (v2 = commit `1c677bdc`, tags `v1`/`v2`, repo set private; seed column not exposed). **Not done:** push the updated card and decide when to make the repo public (needs the owner's write token and go-ahead; `analysis/14_upload_to_hf.py --readme_only --retag_v2 --go`). |

**Remaining work, in order (updated 2026-10-10):** (1) push the updated card and decide public/private; (2) push the local pykakuro tree (generator fixes applied 2026-10-10, cleaning scripts, README) to GitHub: owner's step, until then the public repo does not reproduce the data; (3) paper text: replace the uniqueness claim, add the v1→v2 table, the selection-effect note, the row/column-property note and the difficulty definition; (4) optionally, an independent re-verification of the uploaded files by someone who did not build them.

The sections below are the original plan, kept for the record; where they say "pending" the status table above supersedes them.


Addresses the reviewer point: *"Dataset validation remains incomplete, particularly for duplicate and
near-duplicate filtering"*, and supplies the difficulty labels that Plan 2 (`../kakuro-craze/EVALUATION_PLAN.md`)
needs for stratification. Written 2026-10-09. Nothing below has been run yet except Section 0.

## 0. What is already known (evidence, not conclusions)

| Fact | Evidence |
|---|---|
| HF `Apaxdor/kakuro_kraze` is **public now** (checked 2026-10-09: `private=false`, `gated=false`, sha 2531b9b, last modified 2026-05-17). | Earlier the same API calls returned 401. The 9 parquet files equal the local `kakuro_kraze` (`analysis/10_compare_hf_to_local.py`), i.e. HF still serves the old, partly non-unique data. |
| No token is needed to read it; none was found on this machine or DCC (a *write* token is needed to upload v2). | See `DATASET_CLEANING.md` §7. |
| Local data = 3 sizes × (50k train / 5k val / 5k test). | `analysis/00_split_stats.py`. Within-split: 0 duplicate puzzle strings, 0 duplicate solutions. |
| **Raw-string overlap between splits is 0** (train∩val, train∩test, val∩test, all three sizes). | `analysis/02_exact_split_overlap.py`. This is only the *weakest* check (byte-identical strings); shifted/transposed copies and near-duplicates are what Stages C–E test. |
| **Many puzzles carry the solver-timeout signature.** | `analysis/01_timeout_signature.py`: test-set fraction with `difficulty == 0.05·ln(5·10⁵) + 0.01·num_entry_squares` is **4.9 % (9×9), 15.7 % (11×11), 55.7 % (15×15)**. That value is exactly what `solve()` writes on `KeyboardInterrupt` ([kakuro.py:229-232](src/pykakuro/kakuro.py)). |

### Why the timeout signature matters (potential validity bug)
- `generate_dataset.py` appends a row **regardless of whether `solve()` succeeded** (rows are built from `puzzle` before `err` is looked at), and sets `is_exclusive = puzzle.is_exclusive and len(puzzle.solutions) <= 1`.
- `_solve` enumerates *all* solutions, so for a **finished** solve that check is meaningful. For a **timed-out** solve, `solutions` holds 0 or a partial list, so `len(...) <= 1` is true and the puzzle is labelled exclusive without uniqueness ever being established.
- `clean_kakuro_dataset_for_hf.py` filters only on `is_exclusive`, so those puzzles are in the released splits.
- Consequence if confirmed: the ground-truth solution is the generator's `master_solution` (always a *valid* solution) but may not be *the unique* solution, so a correct alternative fill would be scored wrong. This would depress, not inflate, accuracy, but it undermines "exact-match grid accuracy" and the 15×15 numbers most.
- Also: the `difficulty` field is a capped quantity (the 15×15 median jumps 0.74 → 1.39 because of the cap), so it **cannot be used for stratification**. Step 3 replaces it.
- **Confirmed by Stage B (run 2026-10-09)** — see §0b.

## 0b. Stage B results (independent CP-SAT check; `analysis/03_verify_uniqueness.py`, `04_summarize_uniqueness.py`, `out/uniqueness_summary.txt`)

Checked: all 5 000 val + 5 000 test puzzles per size, and a random 5 000-per-size train sample (45 000 puzzles total). 0 solver errors, 0 undecided, 0 structural problems, and the stored solution satisfies every rule in 100 % of puzzles.

| Split / size | n | independently unique | **multiple solutions** | multiple ⇔ timeout signature? |
|---|---|---|---|---|
| test 9×9 | 5000 | 95.12 % | **4.88 %** | yes (244/244) |
| test 11×11 | 5000 | 84.26 % | **15.74 %** | yes (787/787) |
| test 15×15 | 5000 | 44.34 % | **55.66 %** | yes (2783/2783) |
| val 9 / 11 / 15 | 5000 each | 94.9 / 83.0 / 42.6 % | 5.1 / 17.0 / 57.4 % | yes |
| train sample 9 / 11 / 15 | 5000 each | 95.3 / 83.5 / 42.6 % | 4.7 / 16.5 / 57.4 % | yes |

- Across all 45 000 checked puzzles: **every** timeout-signature puzzle (11 725) has ≥ 2 solutions and **every** other puzzle (33 275) is unique. The generator's `is_exclusive` flag, which the paper's uniqueness claim rests on, is wrong for exactly the puzzles whose solve timed out.
- Consequence: the published "verified unique" claim is false for 5 % / 16 % / 56 % of 9 / 11 / 15 puzzles. For those, exact-match against the stored solution can mark a *valid* alternative answer wrong, so reported grid accuracy is biased downward (most at 15×15).
- Caveat for fixing it: timeouts are the harder puzzles, so the `clean` subset (test: 4756 / 4213 / 2217 puzzles) is **easier** than the full set. Report both, and add the constraint-valid metric to evaluation.
- Length-1 runs are ~64–68 % of all runs (mean over puzzles), i.e. many cells are determined directly by a single-cell clue. This should be disclosed and its effect on cell accuracy estimated (Stage F).

## 0c. Provenance checks
- **Local HF copy:** none (no hub cache snapshot). Two local copies exist: `ar-diffusion-2d/data/kakuro_kraze/` (parquet, written by `clean_kakuro_dataset_for_hf.py`, 50k/5k/5k per size) and `kakuro_craze/` (older `save_to_disk`, differently sized). They are **different samples**: only 126–248 of 5 000 val/test puzzles overlap, and 9.8–11.5 k of train. `kakuro_kraze` is the one matching the loader default `Apaxdor/kakuro_kraze`; treat it as canonical but confirm against HF when access is verified. The older `kakuro_craze` should not be used for any reported number.
- **GitHub `data-hound/pykakuro`** (public, forked from `ianepperson/pykakuro`, last commit 2026-04-23 "updated install instructions"): its `generate_dataset.py` is an **older version** (no `--board_size/--start_id/--puzzle_count` args, different save path) than the local one that generated the data, and `clean_kakuro_dataset_for_hf.py` (the split/`puzzle_id` script) is **not in the repo** (404). Its `kakuro.py` has an active `pdb.set_trace()` at line 404 (commented out locally). It contains the same timeout/`is_exclusive` bug. So the public code cannot reproduce the released splits; the local changes are uncommitted/unpushed (we do not push — see memory note on the local `publish` branch).

## 1. Resource cap and resume mechanism (per CLAUDE.md)

- **Cap (as run):** 24 workers (limit 32) max on `pse-tdunnlab-dt01` (128 cores / 503 GB, shared). Before launch and every ~10 min: `uptime` and `/sys/class/hwmon/*/temp1_input` (k10temp); back off if load > ~64 or die temp is high. If DCC ssh is restored, the same scripts run via `ssh dcc-agent` (CPU only, no GPU needed anywhere in this plan).
- **Resume:** every stage writes `analysis/out/<stage>/<split>_<chunk>.parquet` per chunk of 500 puzzles, and a runner skips chunks whose output exists (write to `*.tmp`, `os.replace` on completion). Each puzzle is solved in its own subprocess-with-timeout so one pathological puzzle cannot kill the pool. Run detached (`nohup … &`) with logs in `analysis/logs/`.
- Total expected cost: minutes for hashing/MinHash, a few CPU-hours for the independent solver (30k val+test puzzles + sampled train).

## 2. Stages (priority order)

All scripts go in `pykakuro/analysis/`; every number reported in a paper/rebuttal must come from a script there, never from scratch code.

### Stage A — Establish the canonical copy
1. Local copies: `ar-diffusion-2d/data/kakuro_kraze/grid{9,11,15}/*.parquet` (what `clean_kakuro_dataset_for_hf.py` writes) and `kakuro_craze/` (`save_to_disk` format, older). Compare `puzzle_id` sets; declare one canonical.
2. Raw pool: `kakuro_mania/` has 105 parts = 350 000 per size, but `run_kakuro_gen.sh` shows one 250 000 run starting at seed 100000 (earlier runs presumably produced the rest). Record the seed ranges per size and verify seeds are unique and non-overlapping across runs. Note `gen_random` uses `if seed:` so **seed 0 is treated as unseeded**, and `random.seed` is process-global.
3. When token access works: download the HF repo and check its `puzzle_id` set equals the local canonical set (this is what reviewers will actually see).

### Stage B — Independent validity + uniqueness (the potential bug)
1. Write `verify_puzzle` / `verify_solution` (the `TODO` in `pykakuro/TODO`): from the puzzle string alone, derive runs, check clue sums, digits 1–9, no repeats within a run, every white cell in ≥ 1 run, and that the stored solution satisfies it.
2. Independent **solution counter** written separately from `kakuro.py`: CP-SAT (OR-Tools) or pysat — solve, block the found solution, solve again (count up to 2). Neither is installed in `ardiff2d` (`pip install ortools` into a new env; confirm with you first). Record `status ∈ {unique, multiple, limit}` with a deterministic limit; never silently coerce. Run on **all** val+test puzzles, not only timeout-signature ones, since pykakuro's pruning could also miscount puzzles it did finish.
3. Run on **all val + test (10 000 per size = 30 000 puzzles across the 3 sizes)** and a **random 5 000-per-size sample of train**. Report, per size, split by the timeout-signature flag: `% unique`, `% multiple`, `% undecided`. This decides whether the bug costs anything.
4. Structural audit in the same pass: % of runs of length 1 (the sample board has many, e.g. `(1,0),1,0`, which make cells trivially determined and inflate cell accuracy), run-length histogram, % white cells forced by propagation alone.
5. Policy output: a `clean` flag per puzzle = valid ∧ unique-verified. Release/report both the full test set and the `clean` subset. If a size loses too many puzzles (likely 15×15), say so and regenerate more with the fix below.

### Stage C — Exact + canonical duplicates (within and across splits)
Canonicalise before hashing; the existing `analyze_duplicates.py` hashes the raw token tuple only.
1. Crop to the bounding box of non-black cells (the sample boards have dead black rows/cols, so a shifted copy defeats raw hashing).
2. Apply the 8 grid symmetries where valid: transpose (swapping the (right,down) clue pair) is the semantics-preserving one; also test flips/rotations as *layout* equivalence only. Hash the lexicographically smallest form.
3. Hash **three granularities**: (a) full puzzle, (b) layout mask only, (c) layout + clues (puzzle without solution). Report train∩val, train∩test, val∩test for each, per size, plus within-split.
4. Also hash solutions (grid of digits + layout) — the test-set answer leaking into train is the memorisation risk.

### Stage D — Near-duplicates
`analyze_duplicates.py` as written (a) loads from the private HF repo and (b) buckets by *identical* clue mask, so it can never find near-duplicates with different layouts. Replace with:
1. Canonical form from Stage C → tokens per cell.
2. **MinHash/LSH** over cell-position shingles (e.g., 3×3 windows of tokens) to propose candidates across all splits, then verify candidates with exact Hamming / edit distance on the canonical grid. Report counts at thresholds ≤ 2, ≤ 5, ≤ 10 % of cells, per split pair. Test→train nearest-neighbour distance histogram (this is the headline plot).
3. Keep it CPU-bound with ≤ 32 workers; chunk by test puzzle so it resumes.

### Stage E — Component-level overlap (the memorisation number)
Boards decompose into independent connected regions (white cells linked via shared runs). Canonicalise each component (clues + layout, translation/transposition invariant), then report for each test puzzle the **fraction of its white cells lying in components that appear verbatim in train**, and the same with the solution digits included. Report the distribution, not only the mean. Small components will legitimately recur; report the size at which overlap vanishes.

### Stage F — Distribution description (supports "fixed generator" criticism)
Per size: black-cell density, #runs, run-length distribution, clue-sum distribution, `num_entry_squares`, and the solver-based difficulty from Stage B (propagation-only solvable fraction, search nodes). Compare train vs test with a simple two-sample test per statistic. This both documents what "the generator distribution" is and produces the difficulty strata that Plan 2 consumes (`analysis/out/difficulty_strata.parquet`: `puzzle_id, size, split, clean, tertile, propagation_frac, nodes`).

### Stage G — Fixes (only if Stage B/C/D show a problem)
- Generator, `generate_dataset.py` bugs found by reading it:
  1. Rows are appended whether or not `solve()` succeeded; `is_exclusive` is set from a possibly partial `solutions` list (see §0).
  2. `f()` returns the *class* `kakuro.SolutionUnsolvedException`, so `isinstance(err, Exception)` is False: timeouts are never counted and every `Failure perc` line in `logs/*.out` **understates** the true failure rate. If the paper quotes a rejection rate from those logs, it is wrong.
  3. Rows where `check_solution` raised are also appended.
  4. The 5 s timeout is wall-clock under pool load, so whether a puzzle times out (hence `is_exclusive`) depends on machine load and is not reproducible from the seed.
  5. `if seed:` treats seed 0 as unseeded; `random.seed` is process-global.
  Fix: record `solve_finished` per row, drop or flag unfinished rows, set `is_exclusive` only when finished, use a node/step budget instead of wall-clock, and regenerate to refill with the unchanged seeds-per-size layout.
- Splits: remove train items within threshold of any val/test item (decontaminate train, never the test), and record counts removed. Publish the clean split under a **new version name** and keep `puzzle_id` stable.
- Do **not** push anything to GitHub (`publish` branch is local). The HF upload is a separate, explicit step requiring your go-ahead.

## 3. Deliverables
- `analysis/` scripts + `analysis/out/` parquet/JSON + `analysis/REPORT.md` (tables: validity, duplicates by granularity and split pair, near-dup histogram, component overlap).
- `analysis/out/difficulty_strata.parquet` and `analysis/out/clean_flags.parquet` for Plan 2.
- A short "Dataset validation" paragraph + table for the paper/rebuttal.

## 4. Order of work
1. Stage A (+ your token test) → 2. Stage B (decides whether anything is broken) → 3. Stage C → 4. Stage F (needed by Plan 2) → 5. Stage D → 6. Stage E → 7. Stage G if needed.

## 4b. Status (2026-10-09)
**Update:** v2 splits for 9×9, 11×11 and 15×15 are built and documented in `DATASET_CLEANING.md` (decision: regenerate/replace non-unique puzzles; unique-only). Stages A, B, C, D (LSH, 0 pairs), E and G(partly) are done for v2; Stage F (solver-based difficulty) remains.

Done: Stage B (all val/test; 5 k train sample/size), exact split overlap, Stage A local-copy comparison. Ran detached with 24 workers; the whole job (90 chunks) finished within about a minute, before the watchdog's second 30 s poll, so the watchdog logged a single reading (load 3.2, CPU 44 °C, GPU 37 °C) and never throttled. The watchdog is untested under real load; it needs a test before the longer Stage D/E runs.
Next: C (canonical dups) → F (difficulty strata; need solver nodes/propagation fraction and the `clean` flag, which Stage B already supports) → D → E → G.

## 5. Open questions for you
- You confirmed the paper claims uniqueness based on the generator flag. Stage B shows that claim does not hold for the timed-out puzzles (§0b). Decision needed: reword the claim and report full vs. `clean` results, and/or regenerate the affected puzzles (I will not modify or upload the dataset without your go-ahead).
