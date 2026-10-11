#!/usr/bin/env python3
"""How much does the dataset's row/column rule simplify the puzzles? READ-ONLY on the published test splits.

Every solution in the dataset has distinct digits across each whole row and column (stronger than the Kakuro rules, which only require distinct digits inside a run). Here the
same deterministic solver as the difficulty score (11_solver_difficulty.py: digit-set propagation per run, then most-constrained-cell backtracking) is run twice on each puzzle:
  standard   run-level rules only (what the task prompt states)
  with rule  additionally, a digit fixed in a cell is removed from every other cell of its row and column
and compares the share of white cells fixed by propagation alone, the share of puzzles solved by propagation alone, and the search nodes needed to prove the solution unique.
Writes out/rowcol_ablation_<size>.parquet and out/rowcol_ablation_summary.json.  Run: python -I 23_rowcol_rule_ablation.py --workers 16"""
import argparse, importlib.util, json, os, sys
from multiprocessing import Pool
import numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("v11", os.path.join(here, "11_solver_difficulty.py")); v11 = importlib.util.module_from_spec(spec); sys.modules["v11"] = v11; spec.loader.exec_module(v11)
v03 = v11.v03
V2 = v11.V2
NODE_CAP = 200000


def solve(runs, white, rc):
    """(fixed_frac, solved_by_propagation, nodes, status). With rc, a singleton digit is also removed from the rest of its row and column."""
    idx = {p: i for i, p in enumerate(white)}
    runs_i = [(t, [idx[p] for p in cs]) for t, cs in runs]
    cell_runs = [[] for _ in white]
    for ri, (_, cs) in enumerate(runs_i):
        for p in cs: cell_runs[p].append(ri)
    lines = [[] for _ in white]
    if rc:
        for i, (r, c) in enumerate(white):
            lines[i] = [idx[q] for q in white if q != (r, c) and (q[0] == r or q[1] == c)]

    def prop(dom, queue):
        while True:
            if not v11.propagate(dom, runs_i, cell_runs, queue): return False
            if not rc: return True
            changed = set()
            for i, d in enumerate(dom):
                if d & (d - 1) == 0:
                    for j in lines[i]:
                        if dom[j] & d:
                            dom[j] &= ~d
                            if dom[j] == 0: return False
                            changed.add(j)
            if not changed: return True
            queue = {ri for j in changed for ri in cell_runs[j]}

    dom = [0b1111111110] * len(white)
    if not prop(dom, list(range(len(runs_i)))): return 0.0, False, 0, "none"
    fixed = sum(1 for d in dom if d & (d - 1) == 0) / max(1, len(dom)); by_prop = fixed == 1.0
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
            if rc and any(vals[j] == vals[i] for i in range(len(vals)) for j in lines[i]): return
            sols.append(vals); return
        i = best[1]
        for d in range(1, 10):
            if dom[i] >> d & 1:
                nd = list(dom); nd[i] = 1 << d
                if prop(nd, list(cell_runs[i])): rec(nd)

    rec(dom)
    return fixed, by_prop, nodes[0], ("limit" if nodes[0] > NODE_CAP else ("multiple" if len(sols) >= 2 else ("unique" if len(sols) == 1 else "none")))


def work(t):
    pid, puzzle = t
    try:
        runs, white, _ = v03.runs_of(v03.parse(puzzle))
        a = solve(runs, white, False); b = solve(runs, white, True)
        return dict(puzzle_id=pid, std_fixed=a[0], std_by_prop=a[1], std_nodes=a[2], std_status=a[3], rc_fixed=b[0], rc_by_prop=b[1], rc_nodes=b[2], rc_status=b[3])
    except Exception as e:
        return dict(puzzle_id=pid, std_status="error:" + type(e).__name__)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--workers", type=int, default=16); ap.add_argument("--sizes", nargs="+", type=int, default=[9, 11, 15]); ap.add_argument("--limit", type=int, default=None); a = ap.parse_args()
    out = os.path.join(here, "out"); os.makedirs(out, exist_ok=True); summary = {}
    with Pool(a.workers, maxtasksperchild=300) as pool:
        for n in a.sizes:
            fn = f"{out}/rowcol_ablation_{n}{'_smoke' + str(a.limit) if a.limit else ''}.parquet"
            if not os.path.exists(fn):
                t = pd.read_parquet(f"{V2}grid{n}/test.parquet", columns=["puzzle_id", "puzzle"]);
                if a.limit: t = t.head(a.limit)
                df = pd.DataFrame(pool.map(work, list(zip(t.puzzle_id, t.puzzle)), chunksize=20)); df.to_parquet(fn + ".tmp"); os.replace(fn + ".tmp", fn)
            d = pd.read_parquet(fn); ok = d[(d.std_status == "unique") & (d.rc_status == "unique")]
            summary[str(n)] = dict(puzzles=int(len(d)), both_unique=int(len(ok)), std_limit=int((d.std_status == "limit").sum()), rc_limit=int((d.rc_status == "limit").sum()),
                                   cells_fixed_by_propagation_std=float(ok.std_fixed.mean()), cells_fixed_by_propagation_rule=float(ok.rc_fixed.mean()),
                                   solved_by_propagation_std=float(ok.std_by_prop.mean()), solved_by_propagation_rule=float(ok.rc_by_prop.mean()),
                                   median_nodes_std=float(ok.std_nodes.median()), median_nodes_rule=float(ok.rc_nodes.median()), p90_nodes_std=float(ok.std_nodes.quantile(.9)), p90_nodes_rule=float(ok.rc_nodes.quantile(.9)),
                                   share_needing_search_std=float((~ok.std_by_prop).mean()), share_needing_search_rule=float((~ok.rc_by_prop).mean()))
            print(n, json.dumps(summary[str(n)]), flush=True)
    json.dump(summary, open(f"{out}/rowcol_ablation_summary{'_smoke' if a.limit else ''}.json", "w"), indent=1)
