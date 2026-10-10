"""Independent validity and uniqueness checks for Kakuro puzzles in the dataset string format.

Nothing here uses kakuro.py's solver. Cell codes in a puzzle string: 0 black, 1 empty white cell, (right_sum, down_sum) clue cell (0 = no clue
in that direction); in a solution string the white cells hold the digits 1-9. Rules: every run sums to its clue and has distinct digits.

  count_solutions   OR-Tools CP-SAT, enumerates up to 2 solutions (deterministic-time limit, never wall-clock): unique / multiple / none / limit
  own_solver        propagation (digit-set masks) + most-constrained-cell backtracking, no OR-Tools; also yields the difficulty metrics
  block_resolve     CP-SAT with the stored solution forbidden; must be INFEASIBLE
  check_puzzle      all three on one (puzzle, solution) pair

The analysis/ scripts of the v2 pipeline contain the same logic (03_verify_uniqueness.py, 11_solver_difficulty.py); test/test_v3.py checks that
this module agrees with the stored v2 labels.
"""
import ast
import itertools

NODE_CAP = 200000


def parse(s):
    return [ast.literal_eval(l.strip()) for l in s.strip().splitlines() if l.strip()]


def runs_of(grid):
    """Return (runs, white_cells, problems); runs = list of (clue_sum, [(r, c), ...])."""
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
    """True if the solution grid satisfies every run (digits 1-9, distinct, right sum)."""
    for total, cells in runs:
        vals = [sol[r][c] for r, c in cells]
        if not all(isinstance(v, int) and 1 <= v <= 9 for v in vals):
            return False
        if len(set(vals)) != len(vals) or sum(vals) != total:
            return False
    return True


def count_solutions(runs, white, det_limit=20.0):
    """CP-SAT: enumerate up to 2 solutions. Returns (status, [solution dicts]); status in unique / multiple / none / limit."""
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
    s.parameters.max_time_in_seconds = 10 * det_limit + 60   # safety net only; the deterministic limit decides
    st = s.Solve(m, CB())
    if len(sols) >= 2:
        return "multiple", sols
    if st == cp_model.OPTIMAL:
        return ("unique" if len(sols) == 1 else "none"), sols
    if st == cp_model.INFEASIBLE:
        return "none", sols
    return "limit", sols


def block_resolve(runs, white, sol, det_limit=20.0):
    """CP-SAT with the stored solution forbidden. 'infeasible_ok' means no other solution exists."""
    from ortools.sat.python import cp_model
    m = cp_model.CpModel(); v = {p: m.NewIntVar(1, 9, "") for p in white}
    for t, cs in runs:
        xs = [v[p] for p in cs]; m.AddAllDifferent(xs); m.Add(sum(xs) == t)
    diffs = []
    for p in white:
        b = m.NewBoolVar(""); m.Add(v[p] != sol[p]).OnlyEnforceIf(b); m.Add(v[p] == sol[p]).OnlyEnforceIf(b.Not()); diffs.append(b)
    m.AddBoolOr(diffs)
    s = cp_model.CpSolver(); s.parameters.num_workers = 1; s.parameters.max_deterministic_time = det_limit
    st = s.Solve(m)
    return {cp_model.INFEASIBLE: "infeasible_ok", cp_model.OPTIMAL: "ALTERNATIVE_FOUND", cp_model.FEASIBLE: "ALTERNATIVE_FOUND"}.get(st, "limit")


COMBOS = {}
for _n in range(1, 10):
    for _c in itertools.combinations(range(1, 10), _n):
        COMBOS.setdefault((_n, sum(_c)), []).append(sum(1 << d for d in _c))


def _propagate(dom, runs, cell_runs, queue):
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


def own_solver(runs, white):
    """Propagation + MRV backtracking, counting solutions up to 2. Returns (metrics, first_solution_or_None).
    metrics: own_status (unique / multiple / limit / none), prop_fixed_frac (cells fixed by root propagation), search_nodes (cap NODE_CAP)."""
    idx = {p: i for i, p in enumerate(white)}
    runs_i = [(t, [idx[p] for p in cs]) for t, cs in runs]
    cell_runs = [[] for _ in white]
    for ri, (_, cs) in enumerate(runs_i):
        for p in cs: cell_runs[p].append(ri)
    dom = [0b1111111110] * len(white)
    if not _propagate(dom, runs_i, cell_runs, range(len(runs_i))):
        return dict(own_status="none", prop_fixed_frac=0.0, search_nodes=0), None
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
                if _propagate(nd, runs_i, cell_runs, cell_runs[i]): rec(nd)

    rec(dom)
    st = "limit" if nodes[0] > NODE_CAP else ("multiple" if len(sols) >= 2 else ("unique" if len(sols) == 1 else "none"))
    return (dict(own_status=st, prop_fixed_frac=fixed, search_nodes=nodes[0]),
            (None if not sols else {white[i]: sols[0][i] for i in range(len(white))}))


def check_puzzle(puzzle, solution, det_limit=20.0):
    """Run every check on one (puzzle, solution) string pair. A puzzle passes iff
    valid and cpsat_status == 'unique' and cpsat_matches_stored and own_status == 'unique' and own_matches_stored and block_resolve == 'infeasible_ok'."""
    g = parse(puzzle); sol = parse(solution)
    runs, white, problems = runs_of(g)
    out = dict(n_white=len(white), n_runs=len(runs), problems=";".join(problems),
               frac_len1_runs=sum(len(cs) == 1 for _, cs in runs) / max(1, len(runs)), stored_valid=stored_ok(runs, sol))
    st, sols = count_solutions(runs, white, det_limit)
    out["cpsat_status"] = st
    out["cpsat_matches_stored"] = bool(st == "unique" and all(sol[r][c] == sols[0][(r, c)] for r, c in white))
    m, own = own_solver(runs, white)
    out.update(m)
    out["own_matches_stored"] = bool(own is not None and all(own[(r, c)] == sol[r][c] for r, c in white))
    out["block_resolve"] = block_resolve(runs, white, {(r, c): sol[r][c] for r, c in white}, det_limit)
    out["passes"] = bool(out["stored_valid"] and not problems and out["cpsat_matches_stored"] and out["own_status"] == "unique"
                         and out["own_matches_stored"] and out["block_resolve"] == "infeasible_ok")
    return out
