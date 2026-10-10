#!/usr/bin/env python3
"""Stage B: independent validity + uniqueness check (CP-SAT, separate from kakuro.py).

For each puzzle: parse the puzzle string, derive runs, check the stored solution against the
rules, then count solutions up to 2 with OR-Tools CP-SAT (deterministic-time limit).

Cell format in the data: 0 = black, 1 = white, (right_sum, down_sum) = clue cell.
Resumable: one output parquet per chunk of CHUNK puzzles; existing chunks are skipped.
Each puzzle is solved inside a worker; exceptions are recorded, never raised.

Run:  python -I 03_verify_uniqueness.py --workers 24 --splits validation test
"""
import argparse, ast, math, os, time
from multiprocessing import Pool
import pandas as pd

_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
DATA = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_kraze/"
CHUNK = 500
CAP = 0.05 * math.log(5 * 10**5)  # solver-timeout difficulty constant in kakuro.py


def parse(s):
    return [ast.literal_eval(l.strip()) for l in s.strip().splitlines() if l.strip()]


def runs_of(grid):
    """Return (runs, white_cells, problems). runs = list of (clue_sum, [(r,c),...])."""
    H, W = len(grid), len(grid[0])
    isw = lambda r, c: 0 <= r < H and 0 <= c < W and grid[r][c] == 1
    runs, problems = [], []
    for r in range(H):
        for c in range(W):
            cell = grid[r][c]
            if isinstance(cell, tuple):
                right, down = cell
                for total, dr, dc in ((right, 0, 1), (down, 1, 0)):
                    if total == 0:
                        continue
                    cells, rr, cc = [], r + dr, c + dc
                    while isw(rr, cc):
                        cells.append((rr, cc)); rr += dr; cc += dc
                    if not cells:
                        problems.append("empty_run")
                    else:
                        runs.append((total, cells))
    white = [(r, c) for r in range(H) for c in range(W) if grid[r][c] == 1]
    covered = {p for _, cs in runs for p in cs}
    if any(p not in covered for p in white):
        problems.append("uncovered_white")
    return runs, white, problems


def stored_ok(runs, sol):
    for total, cells in runs:
        vals = [sol[r][c] for r, c in cells]
        if not all(isinstance(v, int) and 1 <= v <= 9 for v in vals):
            return False
        if len(set(vals)) != len(vals) or sum(vals) != total:
            return False
    return True


def count_solutions(runs, white, det_limit, wall_limit):
    from ortools.sat.python import cp_model
    m = cp_model.CpModel()
    v = {p: m.NewIntVar(1, 9, f"v{p[0]}_{p[1]}") for p in white}
    for total, cells in runs:
        xs = [v[p] for p in cells]
        m.AddAllDifferent(xs)
        m.Add(sum(xs) == total)
    sols = []

    class CB(cp_model.CpSolverSolutionCallback):
        def __init__(self):
            super().__init__()
        def on_solution_callback(self):
            sols.append({p: self.Value(v[p]) for p in white})
            if len(sols) >= 2:
                self.StopSearch()

    s = cp_model.CpSolver()
    s.parameters.enumerate_all_solutions = True
    s.parameters.num_workers = 1
    s.parameters.max_deterministic_time = det_limit
    s.parameters.max_time_in_seconds = wall_limit  # safety net only
    st = s.Solve(m, CB())
    if len(sols) >= 2:
        status = "multiple"
    elif st == cp_model.OPTIMAL:      # search space exhausted
        status = "unique" if len(sols) == 1 else "none"
    elif st == cp_model.INFEASIBLE:
        status = "none"
    else:
        status = "limit"
    return status, sols


def work(args):
    split, size, idx, pid, puzzle, solution, difficulty, nentry, det_limit = args
    t0 = time.time()
    row = dict(split=split, size=size, idx=idx, puzzle_id=pid,
               timeout_signature=bool(abs(difficulty - (CAP + 0.01 * nentry)) < 1e-6))
    try:
        g = parse(puzzle); sol = parse(solution)
        runs, white, problems = runs_of(g)
        row.update(n_white=len(white), n_runs=len(runs), problems=";".join(problems),
                   frac_len1_runs=sum(len(cs) == 1 for _, cs in runs) / max(1, len(runs)))
        row["stored_valid"] = stored_ok(runs, sol)
        status, sols = count_solutions(runs, white, det_limit, 10 * det_limit + 60)
        row["status"] = status
        row["stored_is_found_solution"] = (
            status == "unique" and all(sol[r][c] == sols[0][(r, c)] for r, c in white))
    except Exception as e:  # isolate failures
        row["status"] = "error"; row["error"] = f"{type(e).__name__}: {e}"[:200]
    row["secs"] = time.time() - t0
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--splits", nargs="+", default=["validation", "test"])
    ap.add_argument("--sizes", nargs="+", type=int, default=[9, 11, 15])
    ap.add_argument("--sample", type=int, default=None, help="random sample size per split/size (train)")
    ap.add_argument("--limit", type=int, default=None, help="first N puzzles only (smoke test)")
    ap.add_argument("--data", default=DATA, help="root containing grid<N>/<split>.parquet")
    ap.add_argument("--det_limit", type=float, default=20.0)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "uniqueness"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    with Pool(a.workers, maxtasksperchild=200) as pool:
        for size in a.sizes:
            for split in a.splits:
                df = pd.read_parquet(f"{a.data}grid{size}/{split}.parquet")
                df = df.reset_index().rename(columns={"index": "idx"})
                if a.sample:
                    df = df.sample(min(a.sample, len(df)), random_state=0).sort_values("idx")
                if a.limit:
                    df = df.head(a.limit)
                for c0 in range(0, len(df), CHUNK):
                    fn = f"{a.out}/{split}_{size}_{c0:06d}.parquet"
                    if os.path.exists(fn):
                        continue
                    ch = df.iloc[c0:c0 + CHUNK]
                    tasks = [(split, size, int(r.idx), r.puzzle_id, r.puzzle, r.solution,
                              float(getattr(r, "difficulty", float("nan"))), int(r.num_entry_squares), a.det_limit)
                             for r in ch.itertuples()]
                    rows = pool.map(work, tasks, chunksize=5)
                    pd.DataFrame(rows).to_parquet(fn + ".tmp"); os.replace(fn + ".tmp", fn)
                    print(split, size, c0, pd.Series([r["status"] for r in rows]).value_counts().to_dict(), flush=True)


if __name__ == "__main__":
    main()
