#!/usr/bin/env python3
"""Generate NEW puzzles with the (unchanged) pykakuro generator and keep only independently-unique ones.

Per seed: gen_random(size,size,seed) -> puzzle + generator's master_solution; count solutions (CP-SAT, 03's work());
accept iff status == unique and stored solution == the solver's solution. `difficulty` (legacy field) is then filled
by the old solver with a 30 s timeout (NaN if it times out). Rows use the same schema as kakuro_mania pool parts.
Seeds must not overlap the existing pool (0..349999). Resumable per chunk of seeds; each seed isolated.
Run: python -I 09_generate_unique.py --size 15 --seed_start 350000 --seed_count 200000 --workers 24"""
import argparse, importlib.util, os, sys, math
from multiprocessing import Pool
import pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(here) + "/src")
from pykakuro import kakuro
spec = importlib.util.spec_from_file_location("v03", os.path.join(here, "03_verify_uniqueness.py"))
v03 = importlib.util.module_from_spec(spec); sys.modules["v03"] = v03; spec.loader.exec_module(v03)
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
_sp = importlib.util.spec_from_file_location("kk_property", os.path.join(here, "kk_property.py")); kk_property = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(kk_property)
OUT = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_mania_gen/"

def one(t):
    size, seed = t
    try:
        k = kakuro.gen_random(size, size, seed=seed, is_solved=False)
        p = kakuro.print_lol(k.data, k.x_size, center_cells=False)
        s = kakuro.print_lol(k.master_solution, k.x_size, center_cells=False)
        r = v03.work(("gen", size, seed, str(seed), p, s, 0.0, 0, 20.0))
        if r["status"] != "unique" or not r.get("stored_is_found_solution"):
            return dict(seed=seed, status=r["status"])
        if any(kk_property.violations(s)):
            return dict(seed=seed, status="violates_row_col_distinct")
        diff = float("nan")
        try:
            k2 = kakuro.gen_random(size, size, seed=seed, is_solved=False)
            if k2.solve(timeout=30, timeout_exception=False):
                diff = k2.difficulty
        except Exception:
            pass
        return dict(seed=seed, status="unique", puzzle=p, solution=s, difficulty=diff, min_value=k.min_val,
                    max_value=k.max_val, num_entry_squares=k.num_entry_squares, is_exclusive=True)
    except Exception as e:
        return dict(seed=seed, status="error:" + type(e).__name__)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--seed_start", type=int, required=True); ap.add_argument("--seed_count", type=int, required=True)
    ap.add_argument("--workers", type=int, default=24); ap.add_argument("--chunk", type=int, default=10000)
    a = ap.parse_args(); assert a.seed_start >= 350000, "would overlap the existing pool"
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(".set_cache"): os.chdir(os.path.dirname(here))
    with Pool(a.workers, maxtasksperchild=2000) as pool:
        for s0 in range(a.seed_start, a.seed_start + a.seed_count, a.chunk):
            fn = f"{OUT}board_{a.size}_part_gen_{s0:09d}.parquet"
            if os.path.exists(fn): continue
            rows = pool.map(one, [(a.size, s) for s in range(s0, min(s0 + a.chunk, a.seed_start + a.seed_count))], chunksize=50)
            ok = [r for r in rows if r["status"] == "unique"]
            st = pd.Series([r["status"] for r in rows]).value_counts().to_dict()
            pd.DataFrame(ok).to_parquet(fn + ".tmp"); os.replace(fn + ".tmp", fn)
            print(s0, "tried", len(rows), "accepted", len(ok), st, flush=True)
