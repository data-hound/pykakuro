#!/usr/bin/env python3
"""Deterministic, load-independent difficulty + a second, independent uniqueness check for the v2 data.

(1) Own solver (no OR-Tools, no kakuro.py): domains as 9-bit masks; per-run propagation = keep digits that occur in
    at least one digit-set (distinct digits, right length, right sum) contained in the union of the run's domains,
    plus singleton elimination; run to fixpoint. Metrics:
      prop_fixed_frac  share of white cells fixed by root propagation alone (no guessing)
      search_nodes     nodes visited by MRV backtracking that exhaustively counts solutions up to 2 (cap 200k)
      own_status       unique / multiple / limit ; own solution must equal the stored one
(2) CP-SAT block-and-resolve: forbid the stored solution, require INFEASIBLE (different formulation from 03's enumeration).
Resumable per 2000-row chunk; every puzzle isolated. Run: python -I 11_solver_difficulty.py --size 11 --workers 24"""
import argparse, importlib.util, itertools, os, sys, glob
from multiprocessing import Pool
import pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("v03", os.path.join(here, "03_verify_uniqueness.py"))
v03 = importlib.util.module_from_spec(spec); sys.modules["v03"] = v03; spec.loader.exec_module(v03)
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
V2 = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_kraze_v2/"
COMBOS = {}
for n in range(1, 10):
    for c in itertools.combinations(range(1, 10), n):
        COMBOS.setdefault((n, sum(c)), []).append(sum(1 << d for d in c))
NODE_CAP = 200000

def propagate(dom, runs, cell_runs, queue):
    q = list(queue); inq = set(q)
    while q:
        ri = q.pop(); inq.discard(ri)
        total, cells = runs[ri]
        union = 0
        for p in cells: union |= dom[p]
        allowed = 0
        for m in COMBOS.get((len(cells), total), ()):
            if m & ~union == 0: allowed |= m
        if allowed == 0: return False
        for p in cells:
            nd = dom[p] & allowed
            # singleton elimination
            if nd == 0: return False
            if nd != dom[p]:
                dom[p] = nd
                for r2 in cell_runs[p]:
                    if r2 not in inq: q.append(r2); inq.add(r2)
        for p in cells:
            d = dom[p]
            if d & (d - 1) == 0:
                for o in cells:
                    if o != p and dom[o] & d:
                        dom[o] &= ~d
                        if dom[o] == 0: return False
                        for r2 in cell_runs[o]:
                            if r2 not in inq: q.append(r2); inq.add(r2)
    return True

def solve_count(runs, white):
    idx = {p: i for i, p in enumerate(white)}
    runs_i = [(t, [idx[p] for p in cs]) for t, cs in runs]
    cell_runs = [[] for _ in white]
    for ri, (_, cs) in enumerate(runs_i):
        for p in cs: cell_runs[p].append(ri)
    dom = [0b1111111110] * len(white)
    if not propagate(dom, runs_i, cell_runs, range(len(runs_i))): return dict(own_status="none", prop_fixed_frac=0.0, search_nodes=0), None
    fixed = sum(1 for d in dom if d & (d - 1) == 0) / max(1, len(dom))
    nodes = [0]; sols = []
    def rec(dom):
        nodes[0] += 1
        if nodes[0] > NODE_CAP or len(sols) >= 2: return
        best = None
        for i, d in enumerate(dom):
            if d & (d - 1):
                c = bin(d).count("1")
                if best is None or c < best[0]: best = (c, i)
        if best is None:
            vals = [d.bit_length() - 1 for d in dom]
            for total, cs in runs_i:
                v = [vals[p] for p in cs]
                if len(set(v)) != len(v) or sum(v) != total: return
            sols.append(vals); return
        i = best[1]
        for d in range(1, 10):
            if dom[i] >> d & 1:
                nd = list(dom); nd[i] = 1 << d
                if propagate(nd, runs_i, cell_runs, cell_runs[i]): rec(nd)
    rec(dom)
    st = "limit" if nodes[0] > NODE_CAP else ("multiple" if len(sols) >= 2 else ("unique" if len(sols) == 1 else "none"))
    return dict(own_status=st, prop_fixed_frac=fixed, search_nodes=nodes[0]), (None if not sols else {white[i]: sols[0][i] for i in range(len(white))})

def block_resolve(runs, white, sol):
    from ortools.sat.python import cp_model
    m = cp_model.CpModel(); v = {p: m.NewIntVar(1, 9, "") for p in white}
    for t, cs in runs:
        xs = [v[p] for p in cs]; m.AddAllDifferent(xs); m.Add(sum(xs) == t)
    diffs = []
    for p in white:
        b = m.NewBoolVar(""); m.Add(v[p] != sol[p]).OnlyEnforceIf(b); m.Add(v[p] == sol[p]).OnlyEnforceIf(b.Not()); diffs.append(b)
    m.AddBoolOr(diffs)
    s = cp_model.CpSolver(); s.parameters.num_workers = 1; s.parameters.max_deterministic_time = 20.0
    st = s.Solve(m)
    return {cp_model.INFEASIBLE: "infeasible_ok", cp_model.OPTIMAL: "ALTERNATIVE_FOUND", cp_model.FEASIBLE: "ALTERNATIVE_FOUND"}.get(st, "limit")

def work(t):
    split, idx, puzzle, solution = t
    row = dict(split=split, idx=idx)
    try:
        g = v03.parse(puzzle); sol = v03.parse(solution)
        runs, white, problems = v03.runs_of(g)
        m, own = solve_count(runs, white)
        row.update(m); row["n_white"] = len(white); row["n_runs"] = len(runs)
        row["frac_len1_runs"] = sum(len(c) == 1 for _, c in runs) / max(1, len(runs))
        row["own_matches_stored"] = bool(own is not None and all(own[(r, c)] == sol[r][c] for r, c in white))
        row["block_resolve"] = block_resolve(runs, white, {(r, c): sol[r][c] for r, c in white})
    except Exception as e:
        row["own_status"] = "error:" + type(e).__name__
    return row

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--size", type=int, required=True); ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--limit", type=int, default=None); a = ap.parse_args()
    out = f"{here}/out/difficulty_grid{a.size}"; os.makedirs(out, exist_ok=True)
    with Pool(a.workers, maxtasksperchild=500) as pool:
        for split in ("test", "validation", "train"):
            df = pd.read_parquet(f"{V2}grid{a.size}/{split}.parquet", columns=["puzzle", "solution"])
            if a.limit: df = df.head(a.limit)
            for c0 in range(0, len(df), 2000):
                fn = f"{out}/{split}_{c0:06d}.parquet"
                if os.path.exists(fn): continue
                ch = df.iloc[c0:c0 + 2000]
                rows = pool.map(work, [(split, c0 + i, p, s) for i, (p, s) in enumerate(zip(ch.puzzle, ch.solution))], chunksize=10)
                o = pd.DataFrame(rows); o.to_parquet(fn + ".tmp"); os.replace(fn + ".tmp", fn)
                print(split, c0, o.own_status.value_counts().to_dict(), o.block_resolve.value_counts().to_dict(), flush=True)
