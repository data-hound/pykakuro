#!/usr/bin/env python3
"""KK-Shift: valid, UNIQUE Kakuro puzzles from a shifted generator.

pykakuro.gen_random places a digit only if it is absent from the whole row AND whole column, so every released solution has row- and
column-wide distinct digits (17_global_distinct_check.py: 100 % of puzzles) - stronger than the Kakuro rules, which only require
distinctness inside a run. This generator keeps the layout process (first row/column black, each other cell a white candidate with
probability p) but enforces distinctness ONLY inside runs, so digits may repeat across runs of the same row/column.
Variants:  nodistinct (p = 0.40, same density as the original)   dense (p = 0.50)
Clues, formatting and sums are computed with the same procedure and pykakuro's print_lol as the released data. Every accepted puzzle is checked by CP-SAT
(unique, stored solution == found) and gets the solver-difficulty metrics; the tertile uses the v2 pooled distribution's cut points per size.
Run: python -I 18_generate_shift.py --variant nodistinct --sizes 9 11 15 --target 1500 --workers 16"""
import argparse, importlib.util, os, random, sys
from multiprocessing import Pool
import numpy as np, pandas as pd, xxhash
here = os.path.dirname(os.path.abspath(__file__))
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if os.path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"
sys.path.insert(0, _ROOT + "/Project/pykakuro/src")
from pykakuro import kakuro
def load(name, f):
    spec = importlib.util.spec_from_file_location(name, os.path.join(here, f)); m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m
v03 = load("v03", "03_verify_uniqueness.py"); v11 = load("v11", "11_solver_difficulty.py")
P = {"nodistinct": 0.40, "dense": 0.50}

def gen(size, seed, p):
    rng = random.Random(seed); arr = [0] * (size * size)
    for r in range(1, size):
        for c in range(1, size):
            if rng.random() < p:
                used = set(); cc = c - 1
                while cc >= 1 and arr[r * size + cc]: used.add(arr[r * size + cc]); cc -= 1
                rr = r - 1
                while rr >= 1 and arr[rr * size + c]: used.add(arr[rr * size + c]); rr -= 1
                free = [d for d in range(1, 10) if d not in used]
                if free: arr[r * size + c] = rng.choice(free)
    s = 0                                                    # right sums (same procedure as gen_random)
    for y in range(size):
        for i in range(size + y * size - 1, y * size - 1, -1):
            if arr[i]: s += arr[i]
            elif s: arr[i] = (s, 0); s = 0
    s = 0                                                    # down sums
    for x in range(size):
        for i in range(len(arr) - size + x, -1, -size):
            if arr[i] and type(arr[i]) != type(()): s += arr[i]
            elif s:
                arr[i] = (arr[i][0], s) if type(arr[i]) == type(()) else (0, s); s = 0
    k = kakuro.Kakuro(size, arr, 1, 9, True); k.unsolve()
    return k

def one(t):
    size, seed, p = t
    try:
        k = gen(size, seed, p)
        puz = kakuro.print_lol(k.data, k.x_size, center_cells=False); sol = kakuro.print_lol(k.master_solution, k.x_size, center_cells=False)
        r = v03.work(("shift", size, seed, str(seed), puz, sol, 0.0, 0, 20.0))
        if r["status"] != "unique" or not r.get("stored_is_found_solution"): return dict(seed=seed, status=r["status"])
        d = v11.work(("shift", seed, puz, sol))
        if d.get("own_status") != "unique" or not d.get("own_matches_stored") or d.get("block_resolve") != "infeasible_ok": return dict(seed=seed, status="own_check_failed")
        return dict(seed=seed, status="unique", puzzle=puz, solution=sol, num_entry_squares=int(k.num_entry_squares), solver_prop_fixed_frac=d["prop_fixed_frac"], solver_search_nodes=d["search_nodes"],
                    n_white=d["n_white"], n_runs=d["n_runs"], frac_len1_runs=d["frac_len1_runs"])
    except Exception as e:
        return dict(seed=seed, status="error:" + type(e).__name__)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--variant", required=True, choices=list(P)); ap.add_argument("--sizes", nargs="+", type=int, default=[9, 11, 15])
    ap.add_argument("--target", type=int, default=1500); ap.add_argument("--workers", type=int, default=16); ap.add_argument("--seed_start", type=int, default=2_000_000); a = ap.parse_args()
    out_dir = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_shift/"; os.makedirs(out_dir, exist_ok=True)
    V2 = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_kraze_v2/"
    with Pool(a.workers, maxtasksperchild=500) as pool:
        for size in a.sizes:
            fn = f"{out_dir}{a.variant}_grid{size}.parquet"
            if os.path.exists(fn): print("exists", fn); continue
            rows, tried, seed = [], 0, a.seed_start + {"nodistinct": 0, "dense": 1_000_000}[a.variant] + size * 100_000
            while len(rows) < a.target:
                res = pool.map(one, [(size, s, P[a.variant]) for s in range(seed, seed + 2000)], chunksize=20); seed += 2000; tried += 2000
                rows += [r for r in res if r["status"] == "unique"]
                print(a.variant, size, "tried", tried, "unique", len(rows), flush=True)
            df = pd.DataFrame(rows[:a.target])
            ref = pd.concat(pd.read_parquet(f"{V2}grid{size}/{s}.parquet", columns=["solver_search_nodes", "solver_prop_fixed_frac", "difficulty_score"]) for s in ("train", "validation", "test"))
            nodes, unfixed = np.sort(ref.solver_search_nodes.values), np.sort(1 - ref.solver_prop_fixed_frac.values)
            pr = lambda x, arr: (np.searchsorted(arr, x, "left") + np.searchsorted(arr, x, "right")) / (2.0 * len(arr))      # mid-rank percentile in the v2 pool
            df["difficulty_score"] = (pr(df.solver_search_nodes.values, nodes) + pr(1 - df.solver_prop_fixed_frac.values, unfixed)) / 2
            q = ref.difficulty_score.quantile([1 / 3, 2 / 3]).tolist(); df["difficulty_tertile"] = np.digitize(df.difficulty_score, q).astype(int)
            df["puzzle_id"] = [xxhash.xxh64(s.encode()).hexdigest() for s in df.solution]; df["grid_size"] = size; df["variant"] = a.variant
            df["accept_rate"] = len(rows) / tried; df.to_parquet(fn)
            print("saved", fn, len(df), "accept rate", round(len(rows) / tried, 3), "n_white mean", round(df.n_white.mean(), 1), "tertiles", df.difficulty_tertile.value_counts().sort_index().tolist(), flush=True)
