"""Single source of truth for the dataset property that MUST hold for every puzzle used in any analysis:
in the SOLUTION, the digits of all white cells in each row are pairwise distinct, and likewise for each column
(stronger than Kakuro, which only requires distinctness inside a run). All released v1/v2 puzzles satisfy it (pykakuro.gen_random enforces it).
Loaded by path from other scripts (they run with `python -I`), e.g. importlib.util.spec_from_file_location("kk_property", ".../pykakuro/analysis/kk_property.py")."""
import ast

def violations(sol: str):
    """(rows with a repeated digit, columns with a repeated digit) for one solution string."""
    g = [ast.literal_eval(l.strip()) for l in sol.strip().splitlines() if l.strip()]
    H, W = len(g), len(g[0]); dig = lambda c: isinstance(c, int) and c > 0
    br = sum(1 for r in range(H) if len([x for x in g[r] if dig(x)]) != len({x for x in g[r] if dig(x)}))
    bc = sum(1 for c in range(W) if len([g[r][c] for r in range(H) if dig(g[r][c])]) != len({g[r][c] for r in range(H) if dig(g[r][c])}))
    return br, bc

def count_bad(solutions):
    return sum(1 for s in solutions if any(violations(s)))

def assert_property(solutions, what="data"):
    """Raise unless every solution has row- and column-wide distinct digits."""
    solutions = list(solutions); bad = count_bad(solutions)
    if bad:
        raise SystemExit(f"PROPERTY VIOLATION: {bad} of {len(solutions)} puzzles in {what} do not have row- and column-wide distinct digits. "
                         "This property must hold for all analysis (instruction 2026-10-09). Refusing to continue.")
    return len(solutions)
