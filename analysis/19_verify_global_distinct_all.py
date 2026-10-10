#!/usr/bin/env python3
"""Exhaustive check of the generator property: in every solution, the digits of ALL white cells in each row are pairwise distinct, and the same for each column
(stronger than Kakuro, which only needs distinctness inside a run). Checks EVERY row of: the v2 release (kakuro_kraze_v2), the staged HF upload (hf_staging_v2),
the benchmark subsets used for evaluation, the newly generated 15x15 puzzles, the v1 release, and the KK-Shift sets (expected to violate by construction).
Prints rows checked / violations per file; exit code 1 if any file other than KK-Shift has a violation.
Run: python -I 19_verify_global_distinct_all.py"""
import ast, glob, os, sys
from multiprocessing import Pool
import pandas as pd
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if os.path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"
D = _ROOT + "/Project/ar-diffusion-2d/data/"; B = _ROOT + "/Project/kakuro-craze/benchmark/"

def violations(sol):
    """(#rows with a repeated digit, #cols with a repeated digit)"""
    g = [ast.literal_eval(l.strip()) for l in sol.strip().splitlines() if l.strip()]
    H, W = len(g), len(g[0]); dig = lambda c: isinstance(c, int) and c > 0
    br = sum(1 for r in range(H) if len([x for x in g[r] if dig(x)]) != len({x for x in g[r] if dig(x)}))
    bc = sum(1 for c in range(W) if len([g[r][c] for r in range(H) if dig(g[r][c])]) != len({g[r][c] for r in range(H) if dig(g[r][c])}))
    return br, bc

if __name__ == "__main__":
    files = (sorted(glob.glob(D + "kakuro_kraze_v2/grid*/*.parquet")) + sorted(glob.glob(D + "hf_staging_v2/kakuro_kraze/grid*/*.parquet")) +
             sorted(glob.glob(B + "kk_*.parquet")) + sorted(glob.glob(D + "kakuro_mania_gen/*.parquet")) + sorted(glob.glob(D + "kakuro_kraze/grid*/*.parquet")) + sorted(glob.glob(D + "kakuro_shift/*.parquet")))
    bad_files, tot_rows = [], 0
    with Pool(12) as pool:
        for f in files:
            sols = pd.read_parquet(f, columns=["solution"]).solution.tolist()
            res = pool.map(violations, sols, chunksize=500)
            nb = sum(1 for br, bc in res if br or bc); tot_rows += len(sols)
            tag = "SHIFT(by design)" if "kakuro_shift" in f else ("v1" if "/kakuro_kraze/" in f else "")
            print(f"{f.replace(_ROOT + '/Project/', ''):75s} rows={len(sols):6d} violating_puzzles={nb:5d} {tag}", flush=True)
            if nb and "kakuro_shift" not in f: bad_files.append(f)
    print("\nTOTAL rows checked:", tot_rows, "| non-shift files with violations:", len(bad_files))
    sys.exit(1 if bad_files else 0)
