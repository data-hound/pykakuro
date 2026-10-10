#!/usr/bin/env python3
"""Canonical-form duplicate + near-duplicate analysis for the verified-unique pool of one size.

Canonical form: crop to the bounding box of non-black cells; token per cell: ('B',) black, ('W',) white,
('C',right,down) clue. Two orientations are hashed (identity, and transpose with the clue pair swapped);
the lexicographically smaller repr is canonical. Hash = xxh64 of that repr.
Near-duplicates: MinHash-LSH over the set of (row, col, token) of the canonical grid (Jaccard ~ 1 - Hamming
fraction), candidates verified by exact Hamming distance on same-shape canonical grids.
Component overlap: connected white components, canonicalised the same way.
Run: python -I 07_canonical_dups.py --size 11 --workers 16"""
import argparse, ast, glob, os, sys
from multiprocessing import Pool
import numpy as np, pandas as pd, xxhash
here = os.path.dirname(os.path.abspath(__file__))
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
DATA = _ROOT + "/Project/ar-diffusion-2d/data/"

def parse(s):
    return [ast.literal_eval(l.strip()) for l in s.strip().splitlines() if l.strip()]

def tok(c):
    return ("C", c[0], c[1]) if isinstance(c, tuple) else (("W",) if c == 1 else ("B",))

def canon_grid(g):
    rs = [i for i, row in enumerate(g) if any(c != 0 for c in row)]
    cs = [j for j in range(len(g[0])) if any(row[j] != 0 for row in g)]
    sub = [[tok(g[i][j]) for j in range(cs[0], cs[-1] + 1)] for i in range(rs[0], rs[-1] + 1)]
    tr = [[("C", c[2], c[1]) if c[0] == "C" else c for c in col] for col in zip(*sub)]
    a, b = repr(sub), repr(tr)
    return (sub, a) if a <= b else (tr, b)

def components(g):
    H, W = len(g), len(g[0]); seen = set(); out = []
    for r in range(H):
        for c in range(W):
            if g[r][c] == 1 and (r, c) not in seen:
                st = [(r, c)]; comp = []; seen.add((r, c))
                while st:
                    x, y = st.pop(); comp.append((x, y))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        p = (x + dx, y + dy)
                        if 0 <= p[0] < H and 0 <= p[1] < W and g[p[0]][p[1]] == 1 and p not in seen:
                            seen.add(p); st.append(p)
                out.append(comp)
    return out

def comp_key(g, comp):
    """Translation/transpose-invariant key: whites + the clue (sum,direction,start offset) of each run touching it."""
    S = set(comp); H, W = len(g), len(g[0]); items = []
    for (x, y) in comp:
        # find the clue cell to the left / above that governs this white cell's runs
        yy = y - 1
        while yy >= 0 and g[x][yy] == 1: yy -= 1
        xx = x - 1
        while xx >= 0 and g[xx][y] == 1: xx -= 1
        items.append((x, y, g[x][yy][0] if yy >= 0 and isinstance(g[x][yy], tuple) else -1, yy,
                      g[xx][y][1] if xx >= 0 and isinstance(g[xx][y], tuple) else -1, xx))
    x0 = min(i[0] for i in items); y0 = min(i[1] for i in items)
    a = tuple(sorted((i[0] - x0, i[1] - y0, i[2], i[3] - y0, i[4], i[5] - x0) for i in items))
    b = tuple(sorted((i[1] - y0, i[0] - x0, i[4], i[5] - x0, i[2], i[3] - y0) for i in items))
    return xxhash.xxh64(repr(min(a, b)).encode()).hexdigest(), len(comp)

def work(t):
    pid, puz = t
    g = parse(puz); grid, rep = canon_grid(g)
    comps = [comp_key(g, c) for c in components(g)]
    return pid, xxhash.xxh64(rep.encode()).hexdigest(), len(grid), len(grid[0]), [(h, n) for h, n in comps], \
        [(i, j, t) for i, row in enumerate(grid) for j, t in enumerate(row)]

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--size", type=int, default=11); ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--thr_frac", type=float, default=0.10, help="near-dup Hamming fraction of cells")
    a = ap.parse_args()
    pool = pd.concat(pd.read_parquet(f).drop(columns=["status"], errors="ignore") for f in sorted(glob.glob(f"{DATA}kakuro_mania/board_{a.size}_part_*.parquet")) + sorted(glob.glob(f"{DATA}kakuro_mania_gen/board_{a.size}_part_gen_*.parquet")))
    res = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(f"{here}/out/pool{a.size}/part_*.parquet")))
    uniq = res[res.status == "unique"][["puzzle_id", "seed"]].merge(pool[["seed", "puzzle", "solution"]], on="seed")
    # old splits: tag membership by raw puzzle string
    old = {s: pd.read_parquet(f"{DATA}kakuro_kraze/grid{a.size}/{s}.parquet", columns=["puzzle"]).puzzle for s in ("train", "validation", "test")}
    tag = {}
    for s, ser in old.items():
        for p in ser: tag[p] = s
    uniq["pid"] = uniq.seed.astype(str)
    uniq["old_split"] = uniq.puzzle.map(tag).fillna("none")
    print("verified-unique pool", len(uniq), uniq.old_split.value_counts().to_dict(), flush=True)
    with Pool(a.workers) as p:
        out = p.map(work, list(zip(uniq.pid, uniq.puzzle)), chunksize=200)
    uniq["canon"] = [o[1] for o in out]; uniq["h"] = [o[2] for o in out]; uniq["w"] = [o[3] for o in out]
    uniq["comps"] = [o[4] for o in out]
    dup = uniq.canon.duplicated(keep=False)
    print("canonical exact-duplicate groups: rows in a group =", int(dup.sum()), "| extra copies =", int(uniq.canon.duplicated().sum()), flush=True)
    print("crop shapes:", uniq.groupby(["h", "w"]).size().sort_values(ascending=False).head(5).to_dict(), flush=True)
    # near duplicates via MinHash LSH
    from datasketch import MinHash, MinHashLSH
    ncell = int(np.median(uniq.h * uniq.w)); k = max(1, int(a.thr_frac * ncell)); jt = (ncell - k) / (ncell + k)
    lsh = MinHashLSH(threshold=jt * 0.9, num_perm=128); mh = {}
    for i, o in enumerate(out):
        m = MinHash(num_perm=128)
        for (r, c, t) in o[5]: m.update(f"{r},{c},{t}".encode())
        mh[i] = m; lsh.insert(str(i), m)
    toks = [{(r, c): t for r, c, t in o[5]} for o in out]
    pairs = []
    for i in range(len(out)):
        for j in lsh.query(mh[i]):
            j = int(j)
            if j > i and (uniq.h.iat[i], uniq.w.iat[i]) == (uniq.h.iat[j], uniq.w.iat[j]):
                d = sum(toks[i][q] != toks[j][q] for q in toks[i])
                if d <= k: pairs.append((i, j, d))
    print(f"near-duplicate pairs (Hamming <= {k} of ~{ncell} cells, same crop shape):", len(pairs), flush=True)
    uniq["near_dup_with"] = ""
    for i, j, d in pairs[:100000]:
        uniq.iat[j, uniq.columns.get_loc("near_dup_with")] = str(uniq.pid.iat[i])
    cols = ["pid", "seed", "old_split", "canon", "h", "w", "near_dup_with"]
    uniq[cols + ["comps"]].to_pickle(f"{here}/out/pool{a.size}_canon.pkl")
    pd.DataFrame(pairs, columns=["i", "j", "hamming"]).to_parquet(f"{here}/out/pool{a.size}_neardup_pairs.parquet")
