# pykakuro v3 release notes (prepared 2026-10-10; nothing pushed, tagged or uploaded)

**Code** (branch `v3`, based on the published v2 commit 1adebb2): `families.py` (generators), `verify.py` (gates), `pack/` (production + builder), `test/test_v3.py` (14 tests), GENERATORS.md, CHANGELOG.md.
`pack/pack_report_v3.json` holds the per-config numbers of the pack build (candidates, duplicates, gate failures, nearest-neighbour distances, difficulty).

**Pack** (`ar-diffusion-2d/data/kakuro_v3_ext_staging/`, 21 873 puzzles, 8 configs; `CARD_DRAFT.md` is the draft dataset card; the seed manifest and gate cache are in the SIBLING directory `kakuro_v3_ext_private/` and must not be published; `analysis/14_upload_to_hf.py` uploads a whole folder, so never point it at a directory that contains them).

**Open decisions for the owner**
1. Own-solver cap: 4 884 of 5 757 `symrep_run` 15x15 candidates (and 12 % / 7 % of gated candidates at 11x11 `run` / `rc`) were excluded only because the independent solver exceeded 200 000 nodes; all are CP-SAT-verified unique (enumeration and block-and-resolve). Either keep the strict pack (current), or add a flagged tier of CP-SAT-verified-only puzzles (difficulty known only as ">= cap"), or re-gate with a larger cap (hours of CPU).
2. Evaluation: `eval_hf.py` refuses benchmarks that break the row/column property, so the `*_run` configs cannot be evaluated until that gate is relaxed for them (`blob_run` and `symrep_run` solutions repeat digits across runs).
3. Where to publish the pack (new HF repo vs configs of `Apaxdor/kakuro_kraze`), and the push of branch `v3`.

**Added after review:** the staged pack was audited for duplicates across configs (none) and exact within-config nearest neighbours (`pack/audit_pack.py`, `pack_audit.json`): the symmetric configs are noticeably less diverse than v2 (median nearest neighbour at 26-31 % of cells; 125 / 70 9x9 puzzles within 20 %); disclosed in the card draft and GENERATORS.md. Regeneration from seeds is verified (64 of 64) for ortools 9.15.6755 only.
