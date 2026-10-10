"""Does every solution have DISTINCT digits across each whole row and each whole column (not just within a run)?
Real Kakuro only requires distinctness within a run; pykakuro.gen_random enforces row/column-wide distinctness when placing digits.
Reports, per size/split, the share of puzzles for which that stronger property holds, and how many runs-pairs in a row/col share a digit in real Kakuro terms.
Run: python -I 17_global_distinct_check.py"""
import ast, os
import numpy as np, pandas as pd
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if os.path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"
D = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_kraze_v2/"
def digits(sol):
    g = [ast.literal_eval(l.strip()) for l in sol.strip().splitlines() if l.strip()]
    return [[c if isinstance(c, int) and c > 0 else None for c in row] for row in g]
def global_distinct(sol):
    g = digits(sol); H, W = len(g), len(g[0])
    for r in range(H):
        v = [x for x in g[r] if x]
        if len(v) != len(set(v)): return False
    for c in range(W):
        v = [g[r][c] for r in range(H) if g[r][c]]
        if len(v) != len(set(v)): return False
    return True
for n in (9, 11, 15):
    for s in ("train", "test"):
        x = pd.read_parquet(f"{D}grid{n}/{s}.parquet", columns=["solution"]).solution.head(5000)
        print(f"grid{n} {s}: share of solutions with row- AND column-wide distinct digits = {np.mean([global_distinct(t) for t in x]):.4f}  (n={len(x)})")
