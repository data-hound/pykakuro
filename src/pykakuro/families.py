"""Generator families for Kakuro Kraze v3 (the expansion pack): layouts x digit rules, optional uniqueness repair.

The v2 data comes from kakuro.gen_random (random "blob" layouts, digits distinct across whole rows and columns). This module adds
generators that vary those two choices independently:

  layout   blob   every interior cell is white with probability p (the v2 layout process)
           sym    180-degree rotationally symmetric interior, every run 2..max_run cells, white region 4-connected (human-style)
  digits   rc     digits distinct across each whole row and column (the v2 property)
           run    digits distinct only inside a run (the actual Kakuro rule); repeats across runs of a row/column are allowed
  repair   0      keep the puzzle only if it is already uniquely solvable
           K>0    on a non-unique puzzle, perturb it (change one digit / blacken one cell and its mirror on the cells where two solutions
                  differ), recompute the sums and re-check, up to K steps

Everything is deterministic given (family, size, seed): a local random.Random(seed) is the only source of randomness, the CP-SAT limit is a
deterministic-time limit (never wall-clock), and a CP-SAT 'limit' result is a rejection, counted. Strings are produced with
kakuro.print_lol exactly like the v2 data, so the format is byte-compatible.

generate() returns a dict with status 'ok' (CP-SAT-unique and the stored solution is the one found; run verify.check_puzzle for the full
gate) or a rejection reason: layout_fail, rc_row_too_wide, fill_fail, multiple, none, limit, repair_exhausted.
"""
import random

from . import kakuro, verify

FAMILIES = {
    "sym_rc":     dict(layout="sym",  rc=True,  repair=0),
    "sym_run":    dict(layout="sym",  rc=False, repair=0),
    "symrep_rc":  dict(layout="sym",  rc=True,  repair=150),
    "symrep_run": dict(layout="sym",  rc=False, repair=150),
    "blob_run":   dict(layout="blob", rc=False, repair=0),
}
DEFAULTS = dict(p=0.62, max_run=6, bias=1.0, min_white_frac=0.45, det_limit=2.0, fill_node_cap=50000, layout_tries=30)
BLOB_P = 0.40
FAMILY_INDEX = {k: i + 1 for i, k in enumerate(FAMILIES)}


def seed_for(family, size, k):
    """Disjoint seed ranges per family and size (k < 1,000,000); the v2 pool used 0..549,999 and KK-Shift 2,000,000..3,199,999."""
    return FAMILY_INDEX[family] * 100_000_000 + size * 1_000_000 + k


def segments(W, n):
    """Maximal white segments (length >= 1) across and down, as lists of (r, c)."""
    across, down = [], []
    for r in range(n):
        c = 0
        while c < n:
            if W[r][c]:
                s = c
                while c < n and W[r][c]: c += 1
                across.append([(r, x) for x in range(s, c)])
            else:
                c += 1
    for c in range(n):
        r = 0
        while r < n:
            if W[r][c]:
                s = r
                while r < n and W[r][c]: r += 1
                down.append([(x, c) for x in range(s, r)])
            else:
                r += 1
    return across, down


def connected(W, n):
    whites = [(r, c) for r in range(n) for c in range(n) if W[r][c]]
    if not whites: return False
    seen = {whites[0]}; st = [whites[0]]
    while st:
        r, c = st.pop()
        for q in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= q[0] < n and 0 <= q[1] < n and W[q[0]][q[1]] and q not in seen:
                seen.add(q); st.append(q)
    return len(seen) == len(whites)


def layout_ok(W, n, max_run, min_white):
    across, down = segments(W, n)
    segs = across + down
    return (all(2 <= len(s) <= max_run for s in segs) and sum(map(sum, W)) >= min_white and connected(W, n)
            and not any(W[0]) and not any(W[r][0] for r in range(n)))


def layout_blob(n, rng, p=BLOB_P):
    W = [[False] * n for _ in range(n)]
    for r in range(1, n):
        for c in range(1, n):
            W[r][c] = rng.random() < p
    return W


def _no_short_runs(W, n):
    across, down = segments(W, n)
    return all(len(s) >= 2 for s in across + down)


def layout_sym(n, rng, p, max_run, min_white_frac, tries, line_cap=None):
    """Constructive 180-degree symmetric layout (mirror of (r, c) is (n - r, n - c), rows/cols 1..n-1). Start with every interior cell white,
    (1) cut every run longer than max_run by blackening a cell (and its mirror) that creates no run of length 1 and keeps the white region
    connected, (1b) if line_cap is set (digits distinct across whole rows/columns need <= 9 white cells per row and column) blacken cells in
    over-full rows/columns, then (2) blacken further random cells under the same two conditions until the white share of the interior is <= p.
    Returns None if a long run cannot be cut or the result is too sparse (tries restarts, each with fresh randomness)."""
    min_white = int(min_white_frac * (n - 1) ** 2)
    interior = [(r, c) for r in range(1, n) for c in range(1, n)]

    def try_black(W, r, c):
        if not W[r][c]: return False
        m = (n - r, n - c)
        W[r][c] = W[m[0]][m[1]] = False
        if _no_short_runs(W, n) and connected(W, n): return True
        W[r][c] = True; W[m[0]][m[1]] = True
        return False

    for _ in range(tries):
        W = [[False] * n for _ in range(n)]
        for r, c in interior: W[r][c] = True
        stuck = False
        for _ in range(4 * n * n):
            across, down = segments(W, n)
            long_ = [s for s in across + down if len(s) > max_run]
            if not long_: break
            rng.shuffle(long_)
            progress = False
            for s in long_:
                pos = list(s); rng.shuffle(pos)
                if any(try_black(W, r, c) for r, c in pos): progress = True; break
            if not progress: stuck = True; break
        if stuck: continue
        order = interior[:]; rng.shuffle(order)
        if line_cap:
            over = lambda: any(sum(W[r]) > line_cap for r in range(n)) or any(sum(W[r][c] for r in range(n)) > line_cap for c in range(n))
            for _ in range(20):
                if not over(): break
                for r, c in order:
                    if sum(W[r]) > line_cap or sum(W[x][c] for x in range(n)) > line_cap: try_black(W, r, c)
            if over(): continue
        target = int(p * (n - 1) ** 2)
        for r, c in order:
            if sum(map(sum, W)) <= target: break
            try_black(W, r, c)
        if layout_ok(W, n, max_run, min_white):
            return W
    return None


def fill_digits(W, n, rng, rc, bias, node_cap):
    """Randomized backtracking: distinct digits inside each run (and across each whole row/column if rc). Digit order is a weighted random
    permutation, weight 1 + bias * |d - 5|, so extreme digits (few decompositions, more unique sums) come earlier. Returns {(r, c): digit} or None."""
    across, down = segments(W, n)
    aid, did = {}, {}
    for i, s in enumerate(across):
        for p in s: aid[p] = i
    for i, s in enumerate(down):
        for p in s: did[p] = i
    cells = sorted(aid)
    N = len(cells)
    if N == 0: return None
    ua, ud, ur, uc = [0] * len(across), [0] * len(down), [0] * n, [0] * n
    cl, cur = [None] * N, [0] * N
    i = nodes = 0
    while 0 <= i < N:
        p = cells[i]; r, c = p
        if cur[i]:
            b = ~(1 << cur[i]); ua[aid[p]] &= b; ud[did[p]] &= b
            if rc: ur[r] &= b; uc[c] &= b
            cur[i] = 0
        if cl[i] is None:
            used = ua[aid[p]] | ud[did[p]] | ((ur[r] | uc[c]) if rc else 0)
            keys = sorted(((rng.random() ** (1.0 / (1.0 + bias * abs(d - 5))), d) for d in range(1, 10) if not used >> d & 1), reverse=True)
            cl[i] = [d for _, d in keys]
        if cl[i]:
            d = cl[i].pop(0); b = 1 << d
            ua[aid[p]] |= b; ud[did[p]] |= b
            if rc: ur[r] |= b; uc[c] |= b
            cur[i] = d; i += 1; nodes += 1
            if nodes > node_cap: return None
        else:
            cl[i] = None; i -= 1
    return None if i < 0 else {cells[k]: cur[k] for k in range(N)}


def to_strings(W, digits, n):
    """(puzzle, solution) strings in the dataset format. Clue cells hold (right, down); the clue of a run sits in the cell before it."""
    across, down = segments(W, n)
    clue = {}
    for s in across:
        r, c = s[0]; clue.setdefault((r, c - 1), [0, 0])[0] = sum(digits[p] for p in s)
    for s in down:
        r, c = s[0]; clue.setdefault((r - 1, c), [0, 0])[1] = sum(digits[p] for p in s)
    puz, sol = [], []
    for r in range(n):
        for c in range(n):
            if W[r][c]:
                puz.append(1); sol.append(digits[(r, c)])
            else:
                cell = tuple(clue[(r, c)]) if (r, c) in clue else 0
                puz.append(cell); sol.append(cell)
    return kakuro.print_lol(puz, n, center_cells=False), kakuro.print_lol(sol, n, center_cells=False)


def from_strings(puzzle, solution):
    """Inverse of to_strings: (W, digits, n) from dataset strings (used for tests and for re-deriving structure)."""
    g, s = verify.parse(puzzle), verify.parse(solution)
    n = len(g)
    W = [[g[r][c] == 1 for c in range(n)] for r in range(n)]
    return W, {(r, c): s[r][c] for r in range(n) for c in range(n) if W[r][c]}, n


def rowcol_distinct(W, digits, n):
    """True iff the digits of all white cells of every row, and of every column, are pairwise distinct (the v2 generator property)."""
    for r in range(n):
        v = [digits[(r, c)] for c in range(n) if W[r][c]]
        if len(v) != len(set(v)): return False
    for c in range(n):
        v = [digits[(r, c)] for r in range(n) if W[r][c]]
        if len(v) != len(set(v)): return False
    return True


def _runs(W, digits, n):
    across, down = segments(W, n)
    runs = [(sum(digits[p] for p in s), s) for s in across + down]
    white = [(r, c) for r in range(n) for c in range(n) if W[r][c]]
    return runs, white


def _repair_move(W, digits, n, rng, rc, sym, D, max_run, min_white):
    """One random perturbation anchored on a cell where two solutions differ. Returns (W2, digits2) or None."""
    for _ in range(12):
        p = D[rng.randrange(len(D))]
        if rng.random() < 0.5:
            across, down = segments(W, n)
            sa = next(s for s in across if p in s); sd = next(s for s in down if p in s)
            forb = {digits[q] for q in sa + sd if q != p}
            if rc:
                forb |= {digits[(p[0], c)] for c in range(n) if W[p[0]][c] and c != p[1]} | {digits[(r, p[1])] for r in range(n) if W[r][p[1]] and r != p[0]}
            opts = [d for d in range(1, 10) if d != digits[p] and d not in forb]
            if opts:
                d2 = dict(digits); d2[p] = opts[rng.randrange(len(opts))]
                return W, d2
        else:
            W2 = [row[:] for row in W]
            for q in ((p, (n - p[0], n - p[1])) if sym else (p,)):
                W2[q[0]][q[1]] = False
            if layout_ok(W2, n, max_run, min_white):
                return W2, {q: v for q, v in digits.items() if W2[q[0]][q[1]]}
    return None


def generate(family, size, seed, **over):
    """Generate one candidate for (family, size, seed). Returns dict(status=..., puzzle, solution, meta) for status 'ok', else dict(status=reason)."""
    cfg = {**DEFAULTS, **FAMILIES[family], **over}
    rng = random.Random(seed); n = size
    sym = cfg["layout"] == "sym"
    W = layout_sym(n, rng, cfg["p"], cfg["max_run"], cfg["min_white_frac"], cfg["layout_tries"], cfg.get("line_cap", 9) if cfg["rc"] else None) if sym else layout_blob(n, rng, cfg.get("blob_p", BLOB_P))
    if W is None: return dict(status="layout_fail")
    if cfg["rc"] and (max(sum(row) for row in W) > 9 or max(sum(W[r][c] for r in range(n)) for c in range(n)) > 9):
        return dict(status="rc_row_too_wide")
    digits = fill_digits(W, n, rng, cfg["rc"], cfg["bias"], cfg["fill_node_cap"])
    if digits is None: return dict(status="fill_fail")
    min_white = int(cfg["min_white_frac"] * (n - 1) ** 2)
    steps = 0
    while True:
        runs, white = _runs(W, digits, n)
        st, sols = verify.count_solutions(runs, white, cfg["det_limit"])
        if st == "unique" and all(digits[p] == sols[0][p] for p in white): break
        if st in ("limit", "none") or cfg["repair"] == 0 or steps >= cfg["repair"]:
            return dict(status=st if cfg["repair"] == 0 or st in ("limit", "none") else "repair_exhausted", repair_steps=steps)
        D = [p for p in white if sols[0][p] != sols[1][p]]
        mv = _repair_move(W, digits, n, rng, cfg["rc"], sym, D, cfg["max_run"], min_white)
        if mv is None: return dict(status="repair_exhausted", repair_steps=steps)
        W, digits = mv; steps += 1
    puzzle, solution = to_strings(W, digits, n)
    across, down = segments(W, n)
    lens = [len(s) for s in across + down]
    meta = dict(family=family, grid_size=n, seed=seed, n_white=len(digits), n_runs=len(lens), min_run_len=min(lens), max_run_len=max(lens),
                frac_len1_runs=sum(1 for x in lens if x == 1) / len(lens), repair_steps=steps, rowcol_distinct=rowcol_distinct(W, digits, n),
                layout=cfg["layout"], digit_rule="rc" if cfg["rc"] else "run")
    return dict(status="ok", puzzle=puzzle, solution=solution, meta=meta)
