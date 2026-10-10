#!/usr/bin/env python3
"""How many puzzles that have several solutions under the standard (run-level) Kakuro rules are UNIQUE once the dataset's extra property is imposed as a rule
(all white-cell digits in each whole row distinct, and in each whole column distinct)?
Applies to the v1 test sets (5 000 per size; run-level status from out/uniqueness). Puzzles unique at run level stay unique under the stricter rule (their stored solution
has the property), so the v2 data is valid under both definitions. Run: python -I 20_global_rule_uniqueness.py"""
import glob, importlib.util, os, sys
from multiprocessing import Pool
import pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if os.path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"
spec = importlib.util.spec_from_file_location("v03", os.path.join(here, "03_verify_uniqueness.py")); v03 = importlib.util.module_from_spec(spec); sys.modules["v03"] = v03; spec.loader.exec_module(v03)
D = _ROOT + "/Project/ar-diffusion-2d/data/"

def count(args):
    puzzle, solution = args
    from ortools.sat.python import cp_model
    g = v03.parse(puzzle); runs, white, _ = v03.runs_of(g)
    m = cp_model.CpModel(); v = {p: m.NewIntVar(1, 9, "") for p in white}
    for t, cs in runs: xs = [v[p] for p in cs]; m.AddAllDifferent(xs); m.Add(sum(xs) == t)
    rows, cols = {}, {}
    for (r, c) in white: rows.setdefault(r, []).append(v[(r, c)]); cols.setdefault(c, []).append(v[(r, c)])
    for xs in list(rows.values()) + list(cols.values()):
        if len(xs) > 1: m.AddAllDifferent(xs)                      # the extra, dataset-wide property
    sols = []
    class CB(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            sols.append(1)
            if len(sols) >= 2: self.StopSearch()
    s = cp_model.CpSolver(); s.parameters.enumerate_all_solutions = True; s.parameters.num_workers = 1; s.parameters.max_deterministic_time = 20.0
    st = s.Solve(m, CB())
    return "multiple" if len(sols) >= 2 else ("unique" if st == cp_model.OPTIMAL and len(sols) == 1 else ("none" if st == cp_model.INFEASIBLE else "limit"))

if __name__ == "__main__":
    out = []
    with Pool(16) as pool:
        for n in (9, 11, 15):
            t = pd.read_parquet(f"{D}kakuro_kraze/grid{n}/test.parquet", columns=["puzzle", "solution"]).reset_index().rename(columns={"index": "idx"})
            u = pd.concat(pd.read_parquet(f) for f in glob.glob(f"{here}/out/uniqueness/test_{n}_*.parquet"))[["idx", "status"]]
            t = t.merge(u, on="idx").rename(columns={"status": "run_level"})
            t["global_rule"] = pool.map(count, list(zip(t.puzzle, t.solution)), chunksize=20)
            ct = pd.crosstab(t.run_level, t.global_rule); ct.insert(0, "n", ct.sum(axis=1)); print(f"\n== v1 test {n}x{n}"); print(ct.to_string()); out.append(t.assign(grid=n))
            nu = t[t.run_level == "multiple"]
            print(f"   run-level NON-unique: {len(nu)}; of these UNIQUE once row/column-wide distinctness is imposed: {(nu.global_rule == 'unique').sum()} ({100*(nu.global_rule == 'unique').mean():.1f} %)")
    pd.concat(out)[["grid", "idx", "run_level", "global_rule"]].to_parquet(f"{here}/out/global_rule_uniqueness_v1_test.parquet")
