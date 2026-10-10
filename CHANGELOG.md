# Changelog

## v3 (unreleased)
* `pykakuro.families`: layout x digit-rule x repair generators (`blob_run`, `sym_*`, `symrep_*`), see GENERATORS.md.
* `pykakuro.verify`: self-contained uniqueness/validity gates (CP-SAT count to 2, independent solver, block-and-resolve); needs `ortools`.
* `pack/`: resumable, load-aware production driver (`generate_pack.py`, `run_overnight.sh`) and pack builder with duplicate, gate and nearest-neighbour checks (`build_pack.py`).
* Tests: `test/test_v3.py`.

## v2 (data release, tag `v2` on Hugging Face)
* `gen_random`: local RNG, seed 0 deterministic, global RNG untouched (boards for seed >= 1 unchanged).
* `generate_dataset.py`: `solve_finished`, `solution_check_ok`, correct failure counting, `--out_dir`, `--workers`.
* `analysis/`: independent uniqueness gate, pool verification, duplicate and nearest-neighbour audits, v2 split build, solver difficulty, v1-to-v2 diff mask. See DATASET_CLEANING.md.
