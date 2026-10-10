#!/usr/bin/env python3
"""Stage 1 of the v2 rebuild: independent validity + uniqueness for EVERY puzzle in the raw pool
(ar-diffusion-2d/data/kakuro_mania/board_<N>_part_*.parquet), not only the released splits.
Reuses work() from 03_verify_uniqueness.py. Resumable per chunk of 5000 rows; failures isolated per puzzle.
Run: python -I 05_verify_pool.py --size 11 --workers 24"""
import argparse, glob, importlib.util, os, sys
from multiprocessing import Pool
import pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("v03", os.path.join(here, "03_verify_uniqueness.py"))
v03 = importlib.util.module_from_spec(spec); sys.modules["v03"] = v03; spec.loader.exec_module(v03)
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
POOL = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_mania/"
POOL_GEN = POOL.replace("kakuro_mania/", "kakuro_mania_gen/")
CH = 5000
ap = argparse.ArgumentParser(); ap.add_argument("--size", type=int, required=True)
ap.add_argument("--workers", type=int, default=24); ap.add_argument("--det_limit", type=float, default=20.0)
a = ap.parse_args()
files = sorted(glob.glob(f"{POOL}board_{a.size}_part_*.parquet")) + sorted(glob.glob(f"{POOL_GEN}board_{a.size}_part_gen_*.parquet"))
df = pd.concat(pd.read_parquet(f) for f in files).reset_index(drop=True)
print("pool rows", len(df), "unique seeds", df.seed.nunique(), "unique puzzle strings", df.puzzle.nunique(), flush=True)
out = os.path.join(here, "out", f"pool{a.size}"); os.makedirs(out, exist_ok=True)
with Pool(a.workers, maxtasksperchild=500) as pool:
    for c0 in range(0, len(df), CH):
        fn = f"{out}/part_{c0:07d}.parquet"
        if os.path.exists(fn): continue
        ch = df.iloc[c0:c0 + CH]
        tasks = [("pool", a.size, int(i), str(r.seed), r.puzzle, r.solution, float(r.difficulty),
                  int(r.num_entry_squares), a.det_limit) for i, r in zip(ch.index, ch.itertuples())]
        rows = pool.map(v03.work, tasks, chunksize=20)
        o = pd.DataFrame(rows); o["seed"] = ch.seed.values; o["gen_is_exclusive"] = ch.is_exclusive.values; o["newly_generated"] = (ch.seed.values >= 350000)
        o.to_parquet(fn + ".tmp"); os.replace(fn + ".tmp", fn)
        print(c0, o.status.value_counts().to_dict(), flush=True)
