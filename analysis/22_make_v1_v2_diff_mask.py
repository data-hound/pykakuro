#!/usr/bin/env python3
"""v1 -> v2 diff mask: one row per puzzle_id that is in the v1 release (HF tag v1 = local kakuro_kraze/) or in v2 (kakuro_kraze_v2/), per grid size.
Columns: grid_size, puzzle_id, v1_split, v2_split, change, v1_independent_status, v2_topped_up
  change = same_split | moved_split | removed (in v1 only) | new (in v2 only)
  v1_independent_status = CP-SAT result from the pool-wide verification (out/pool<N>/): unique | multiple | not_in_pool (no row for that id)
No generator seed is written (the seed column is not part of the public release).
Run: python -I 22_make_v1_v2_diff_mask.py   -> out/v1_v2_diff_mask.csv.gz, out/v1_v2_diff_mask_summary.csv"""
import glob, os
import pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if os.path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"
D = _ROOT + "/Project/ar-diffusion-2d/data/"
rows = []
for n in (9, 11, 15):
    v1 = pd.concat([pd.read_parquet(f"{D}kakuro_kraze/grid{n}/{s}.parquet", columns=["puzzle_id", "puzzle"]).assign(v1_split=s) for s in ("train", "validation", "test")])
    v2 = pd.concat([pd.read_parquet(f"{D}kakuro_kraze_v2/grid{n}/{s}.parquet", columns=["puzzle_id", "topped_up"]).assign(v2_split=s) for s in ("train", "validation", "test")])
    assert v1.puzzle_id.is_unique and v2.puzzle_id.is_unique, "duplicate ids inside a release"
    # v1 has no seed: match its puzzle text to the raw pool boards (which carry the seed), then take the pool-wide CP-SAT status of that seed
    boards = pd.concat([pd.read_parquet(f, columns=["puzzle", "seed"]) for f in sorted(glob.glob(f"{D}kakuro_mania/board_{n}_part_*.parquet"))]).drop_duplicates("puzzle")
    st = pd.concat([pd.read_parquet(f, columns=["seed", "status"]) for f in sorted(glob.glob(f"{here}/out/pool{n}/part_*.parquet"))]); st["seed"] = st.seed.astype("int64"); boards["seed"] = boards.seed.astype("int64")
    v1 = v1.merge(boards, on="puzzle", how="left").merge(st.drop_duplicates("seed"), on="seed", how="left").drop(columns=["puzzle", "seed"]).rename(columns={"status": "v1_independent_status"})
    v1["v1_independent_status"] = v1.v1_independent_status.fillna("not_in_pool")
    m = v1.merge(v2, on="puzzle_id", how="outer"); m["v1_independent_status"] = m.v1_independent_status.fillna("")
    m["change"] = "same_split"
    m.loc[m.v1_split.notna() & m.v2_split.notna() & (m.v1_split != m.v2_split), "change"] = "moved_split"
    m.loc[m.v2_split.isna(), "change"] = "removed"
    m.loc[m.v1_split.isna(), "change"] = "new"
    m["grid_size"] = n; m["v1_split"] = m.v1_split.fillna(""); m["v2_split"] = m.v2_split.fillna(""); m["v2_topped_up"] = m.topped_up.map({True: "True", False: "False"}).fillna("")
    rows.append(m[["grid_size", "puzzle_id", "v1_split", "v2_split", "change", "v1_independent_status", "v2_topped_up"]])
mask = pd.concat(rows, ignore_index=True)
os.makedirs(here + "/out", exist_ok=True)
mask.to_csv(here + "/out/v1_v2_diff_mask.csv.gz", index=False)
summ = mask.groupby(["grid_size", "v1_split", "change", "v1_independent_status"]).size().rename("n").reset_index()
summ.to_csv(here + "/out/v1_v2_diff_mask_summary.csv", index=False)
print(len(mask), "rows"); print(mask.groupby(["grid_size", "change"]).size().unstack(fill_value=0).to_string())
rm = mask[mask.change == "removed"]; print("\nremoved v1 puzzles by independent status:"); print(rm.groupby(["grid_size", "v1_independent_status"]).size().unstack(fill_value=0).to_string())
