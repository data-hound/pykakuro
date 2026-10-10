# Generator families (v3)

v2 data comes from one procedure (`kakuro.gen_random`). v3 adds generators that vary its two main choices independently, so results can be checked
against more than one puzzle distribution. Code: `src/pykakuro/families.py`; independent gates: `src/pykakuro/verify.py`; production and release tooling: `pack/`.

| family | layout | digit rule | uniqueness | in the v3 pack |
|---|---|---|---|---|
| `blob_rc` (= v2) | random blobs, white with p = 0.4 | distinct across whole rows and columns | CP-SAT filter | v2 itself (`kakuro.gen_random`, unchanged) |
| `blob_run` | same layouts | distinct only inside a run | CP-SAT filter | yes, sizes 9, 11, 15 |
| `sym_rc`, `sym_run` | 180-degree symmetric, runs 2..6, connected | rc / run | CP-SAT filter only | **no**: random fills of runs this long are almost never unique (yield below 0.1 %) |
| `symrep_run` | as `sym_*` | distinct only inside a run | filter + repair | yes, sizes 9, 11, 15 |
| `symrep_rc` | as `sym_*`, at most 9 white cells per row/column | distinct across whole rows/columns | filter + repair | yes, sizes 9, 11 only (see limits) |

"Row/column-distinct" (`rc`) is the generator artifact of v2: stronger than the Kakuro rules, which only require distinct digits inside a run.
Families with the `run` digit rule do not have it, which is how real Kakuro behaves. `symrep_rc` keeps the artifact but changes the layout, so
(`blob_rc`, `blob_run`, `symrep_rc`, `symrep_run`) form a 2 x 2 that separates the effect of the layout from the effect of the digit rule.

## Algorithms
* **Symmetric layout.** Row 0 and column 0 are black. Interior cells (1..n-1)^2 start white. Runs longer than `max_run` (6) are cut by blackening a cell and its
  180-degree mirror, only if no run of length 1 appears and the white region stays 4-connected; then random cells are blackened the same way until the white share is
  at most `p` (0.62). For `rc`, over-full rows/columns (> 9 white cells) are thinned first.
* **Fill.** Randomized backtracking, digit order a weighted random permutation (weight 1 + bias * |d - 5|, bias 1) so extreme digits, which have fewer decompositions, come
  earlier. Constraint: distinct inside each run (and across the whole row/column for `rc`). Sums are computed afterwards.
* **Repair.** If CP-SAT (counting up to 2 solutions, deterministic-time limit 2) finds two solutions, one random move is applied at a cell where they differ: change that
  cell's digit to another legal digit, or blacken it together with its mirror if the layout stays valid. Sums are recomputed and the puzzle re-checked, up to 150 times.
  The number of steps is stored (`repair_steps`).
* **Determinism.** One `random.Random(seed)` per puzzle; CP-SAT with one worker and a deterministic-time limit; a `limit` result is a rejection (counted), never a guess.
  Seeds: `families.seed_for(family, size, k)`, disjoint across families and sizes and from the v2 pool (0-549 999) and KK-Shift (2 000 000-3 199 999).

## Gates (pack/build_pack.py)
Canonical-duplicate removal (within the pack and against all of v2), `verify.check_puzzle` (CP-SAT count = 1 and equals the stored solution; independent
propagation/backtracking solver agrees; CP-SAT block-and-resolve infeasible), exact nearest-neighbour distance to every v2 puzzle (build fails below 10 % of cells).
Puzzles on which a solver hits its limit are rejected and counted in `pack_report.json`.

## Known limits and biases (read before using the pack)
* Uniqueness is under the standard run-level rules, as in v2.
* Repaired puzzles are not a uniform sample of "all unique symmetric Kakuro": they are what this repair procedure reaches. The same holds for v2 and its generator.
* Puzzles on which the own solver exceeds its 200 000-node cap are rejected, which biases the pack toward easier puzzles; the rate is in `pack_report.json`.
* The pack is much harder for a propagation solver than v2 (no length-1 runs; many more white cells), so difficulty tertiles are relative within a family and size; use
  `difficulty_score_v2ref` to compare against v2.
* `symrep_rc` at 15 x 15 was not generated: with at most 9 white cells per row/column and every run of length 2-6, the constructive layout step almost never succeeds.
* Maximum run length 6 is a design choice, not a Kakuro rule (runs up to 9 are legal).
* All families are synthetic and from one author's code; none replaces a set of human-made puzzles.
