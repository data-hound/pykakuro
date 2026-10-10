# Difficulty metric for Kakuro Kraze v2 (for reviewers and the paper)

Columns: `solver_prop_fixed_frac`, `solver_search_nodes`, `difficulty_score`, `difficulty_tertile`.
Code: `analysis/11_solver_difficulty.py` (computation), `analysis/12_merge_and_compare.py` (score, tertiles), `analysis/13_gpt5mini_rescore.py` (validation).
The generator's earlier `difficulty` field was removed from v2: it was capped at a solver-timeout constant for legacy rows and depended on wall-clock time and machine load for the newly generated rows, so it was neither reproducible nor comparable.

## 1. What is measured
Difficulty is the effort a simple, fully specified, **deterministic constraint solver** needs, not human difficulty and not model difficulty. Two quantities are computed per puzzle:

1. **`solver_prop_fixed_frac`**: the share of white cells whose value is determined by constraint propagation alone (no guessing). 1.0 means the puzzle is solved by propagation.
2. **`solver_search_nodes`**: the number of nodes visited by a backtracking search that, after root propagation, branches on the most constrained cell and exhaustively proves the solution is unique. 1 means propagation solved it with no branching.

## 2. Algorithm
Domains are 9-bit masks over digits 1–9, one per white cell. A *run* is a maximal horizontal or vertical sequence of white cells governed by a clue.

**Propagation (to fixpoint, queue-driven).** For each run of length `n` and sum `S`:
1. Precompute all sets of `n` distinct digits from 1–9 with sum `S`.
2. Keep only sets contained in the union of the run's current cell domains.
3. A cell's new domain is its domain intersected with the union of the kept sets. If no set is kept, or a domain becomes empty, the node is a contradiction.
4. Singleton elimination: a cell fixed to digit `d` removes `d` from the other cells of its run.
Changed cells re-queue their runs until nothing changes.

**Search.** After root propagation, pick the unfixed cell with the smallest domain (ties: first in row-major order), try its digits in ascending order, propagate after each assignment, recurse. Every call of the recursive procedure counts as one node. The search stops at two solutions or when the tree is exhausted (cap 200 000 nodes; never reached, the maximum observed is 9 280). For every v2 puzzle exactly one solution is found and it equals the stored solution.

**Score.** Within each grid size, `difficulty_score = (pct_rank(search_nodes) + pct_rank(1 − prop_fixed_frac)) / 2`, percentile ranks computed over the pooled 60 000 v2 puzzles of that size (ties get average rank). `difficulty_tertile` is 0 / 1 / 2 by the 1/3 and 2/3 quantiles of `difficulty_score` (cut points 0.311 / 0.669 for 9×9, 0.333 / 0.668 for 11×11, 0.344 / 0.663 for 15×15), giving about 20 000 puzzles per tertile and about 1 670 per tertile in each test set.

## 3. Properties
- **Deterministic and load-independent**: no timers; integer node counts; same output on any machine. Rerun with `python -I analysis/11_solver_difficulty.py --size N` then `12_merge_and_compare.py`.
- **Independent of the generator** and of OR-Tools (the uniqueness checkers); it uses only the puzzle text.
- **Tertiles are relative within a grid size.** Do not read "tertile 2" of 9×9 as equal in hardness to "tertile 2" of 15×15. Raw `solver_search_nodes` and `solver_prop_fixed_frac` are comparable across sizes.

Per-size distribution (test sets):

| | 9×9 | 11×11 | 15×15 |
|---|---|---|---|
| puzzles solved by propagation alone (nodes = 1), all of v2 | 19.6 % | 6.7 % | 0.4 % |
| median / 90th pct / max `search_nodes`, all of v2 | 3 / 10 / 3 404 | 5 / 17 / 3 285 | 12 / 38 / 9 280 |
| median `search_nodes` by tertile 0 / 1 / 2 (test) | 1 / 3 / 7 | 2 / 5 / 12 | 6 / 12 / 28 |
| mean `prop_fixed_frac` by tertile 0 / 1 / 2 (test) | 0.98 / 0.89 / 0.75 | 0.95 / 0.87 / 0.76 | 0.92 / 0.85 / 0.78 |
| mean white cells by tertile 0 / 1 / 2 (test) | 22.1 / 24.1 / 26.4 | 35.2 / 37.5 / 40.3 | 69.4 / 72.4 / 75.5 |

Difficulty is correlated with board size within a grid size (more white cells, harder). Report both when stratifying; `n_white` is in the dataset so the effect can be separated by regression.

## 4. Empirical check against a model (existing data, no new runs)
`analysis/13_gpt5mini_rescore.py` matches the existing gpt-5-mini 11×11 outputs (4 945 of the 5 000 v1 test puzzles; 55 batch errors have no output) to v2 puzzles. On the 4 201 matched puzzles that are unique and kept in v2:

| tertile | n | grid accuracy |
|---|---|---|
| 0 (easy) | 1 427 | 96.3 % |
| 1 | 1 389 | 95.9 % |
| 2 (hard) | 1 385 | 93.2 % |

Spearman correlation between `solver_search_nodes` and failure: ρ = 0.065 (p = 2.6e-05, n = 4 201). The ordering is monotone and statistically significant, but the effect is small because gpt-5-mini is near ceiling on these puzzles. **This is weak evidence that solver difficulty tracks model difficulty**; a stronger test needs weaker models and the other sizes (Plan 2). Do not claim more than this.

## 5. Limitations to state in the paper
- It measures one specific solver's effort (propagation by sum/uniqueness sets plus MRV search). Other solvers or humans may rank puzzles differently.
- Since every v2 puzzle is unique and relatively easy for propagation, the range is compressed: median node counts are single or low double digits, and the long tail (hundreds to thousands of nodes) is rare.
- Percentile-rank averaging weights the two components equally by construction; it is a convenience for stratification, not a calibrated difficulty scale.
- Rank ties are common at the low end (many puzzles have nodes = 1), so tertile boundaries inside tied groups are broken only by the other component.
