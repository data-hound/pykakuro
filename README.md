pykakuro - Kakuro Tools For Python

Modified and modernized by Anshuman Sabath 
Copyright (C) 2010 Brandon Thomson <brandon.j.thomson@gmail.com>

These tools can be used to generate, solve, and manipulate (to a limited
extent) Kakuro puzzles.

Can be installed using
```
pip install git+https://github.com/data-hound/pykakuro/
```

```
$ cd pykakuro
$ cd pip install -e .
```

Additional information and an online example can be found at
www.bthomson.com/kakuro.html

## Kakuro Kraze dataset: generation, validation, cleaning (v2)

This repository contains the code that produced and validated the `Apaxdor/kakuro_kraze` dataset (HF tag `v2`).

* **Generator:** `src/pykakuro/generate_dataset.py` (`kakuro.gen_random(size, size, seed=...)`). Digits are placed only if they appear nowhere in the cell's row and column, so every solution has distinct digits across each whole row and column (stronger than the Kakuro rules; `analysis/kk_property.py` checks it). `generate_dataset.py` also records `solve_finished` and `solution_check_ok`; the solver's `is_exclusive` flag is **not** evidence of uniqueness (it was wrong for puzzles whose solve timed out).
* **Uniqueness gate:** `analysis/03_verify_uniqueness.py` (separate code from `kakuro.py`: OR-Tools CP-SAT counts solutions up to 2 and requires the stored solution to be the one found). `analysis/09_generate_unique.py` runs the generator with this gate as the acceptance test.
* **Pipeline for one grid size:** `analysis/run_size.sh SIZE` = pool verification (`05`, `06`), canonical/near-duplicate search (`07`), v2 split build (`08`), re-verification of the written files (`03`). Then `11`/`12` add the deterministic solver-difficulty columns, `21_exact_nn_audit.py` is the exact nearest-neighbour audit, `17`/`19` check the row/column property, `22` writes the v1-to-v2 diff mask.
* **Documentation:** `DATASET_CLEANING.md` (algorithms, numbers, caveats), `DIFFICULTY_METRIC.md`, `DATASET_VALIDATION_PLAN.md`.
* **Seeds:** `gen_random(seed=s)` is reproducible for s >= 1 (verified: 900 pool boards regenerate character for character). The raw pool used seeds 0-349 999; seed 0 was unseeded in the original code and is not reproducible; the fixed code makes it deterministic.
* **Not included:** the raw pool and the dataset files (on HF). The analysis scripts carry the lab's storage paths in a `_ROOT` constant near the top; edit it to run them elsewhere. Needs `pandas`, `pyarrow`, `numpy`, `scipy`, `ortools`, `datasketch`. `analysis/13`, `15`, `16` and `kakuro-craze` result handling belong to the paper's model evaluation and need results that are not part of this repository.

