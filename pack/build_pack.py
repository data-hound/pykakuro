#!/usr/bin/env python3
"""Turn generator candidates into the v3 expansion pack (test-only configs), with every gate recorded.

Per (family, size), candidates in seed order:
  1. canonical duplicates (crop to the non-black bounding box, transpose with clue swap; xxh64) within the pack and against ALL v2 splits are dropped;
  2. verify.check_puzzle (CP-SAT count to 2 + stored solution is the one found + independent propagation/backtracking solver + CP-SAT block-and-resolve)
     must pass; puzzles on which the own solver hits its node cap, or CP-SAT hits its deterministic limit, are rejected AND COUNTED (they bias the pack
     toward easier puzzles, so the rate is reported);
  3. the first N passing puzzles in seed order are kept (so the kept set is not selected on anything but the gates).
Then: puzzle_id (xxh64 of the solution), deterministic difficulty columns (tertile cut points within the family/size, plus the percentile of the
puzzle in the v2 pool of the same size so families can be compared on one scale), and the exact nearest-neighbour audit against v2 train/validation/test
(brute force, both orientations; reported, and the build fails if any pack puzzle is within --gate_frac of the cells of a v2 puzzle).
The generator seed is NOT exposed in the staged files (as in v2); it goes to a private manifest next to the staging directory.

Resumable: gate results are cached per chunk in <staging>/_gate_cache. Resource cap: --workers processes (default 8) at the caller's nice level.
Run: python -I pack/build_pack.py --cand DIR --out STAGING_DIR --N 3000 --workers 8
"""
import argparse, glob, json, os, sys, time
from multiprocessing import Pool
import numpy as np, pandas as pd, xxhash
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(here) + "/src")
import logging; logging.disable(logging.CRITICAL)
from pykakuro import verify, families as F
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if os.path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"
V2 = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_kraze_v2/"
BASE = 46


def tok(c):
    return ("C", c[0], c[1]) if isinstance(c, tuple) else (("W",) if c == 1 else ("B",))


def canon_hash(puzzle):
    g = verify.parse(puzzle)
    rs = [i for i, row in enumerate(g) if any(c != 0 for c in row)]; cs = [j for j in range(len(g[0])) if any(row[j] != 0 for row in g)]
    sub = [[tok(g[i][j]) for j in range(cs[0], cs[-1] + 1)] for i in range(rs[0], rs[-1] + 1)]
    tr = [[("C", c[2], c[1]) if c[0] == "C" else c for c in col] for col in zip(*sub)]
    a, b = repr(sub), repr(tr)
    return xxhash.xxh64(min(a, b).encode()).hexdigest()


def gate(t):
    k, puzzle, solution = t
    try:
        r = verify.check_puzzle(puzzle, solution, det_limit=20.0)
        r["gate_error"] = ""
    except Exception as e:
        r = dict(passes=False, gate_error=type(e).__name__)
    r["k"] = k
    return r


def encode(puzzle):
    g = verify.parse(puzzle); H, W = len(g), len(g[0]); a = np.zeros((H, W), np.int16); t = np.zeros((W, H), np.int16)
    for r in range(H):
        for c in range(W):
            x = g[r][c]
            if isinstance(x, tuple): a[r, c] = 2 + x[0] * BASE + x[1]; t[c, r] = 2 + x[1] * BASE + x[0]
            elif x == 1: a[r, c] = 1; t[c, r] = 1
    return a.ravel(), t.ravel()


_A = _AT = _B = None
def nn_chunk(rng):
    lo, hi = rng
    d1 = np.count_nonzero(_A[lo:hi, None, :] != _B[None, :, :], axis=2)
    d2 = np.count_nonzero(_AT[lo:hi, None, :] != _B[None, :, :], axis=2)
    return lo, np.minimum(d1, d2).min(1)


def nn_audit(pack_puzzles, ref_puzzles, workers, chunk=8):
    global _A, _AT, _B
    e = [encode(p) for p in pack_puzzles]; _A = np.stack([x[0] for x in e]); _AT = np.stack([x[1] for x in e])
    _B = np.stack([encode(p)[0] for p in ref_puzzles])
    out = np.zeros(len(_A), np.int32)
    with Pool(workers) as p:
        for lo, d in p.imap_unordered(nn_chunk, [(i, min(i + chunk, len(_A))) for i in range(0, len(_A), chunk)]): out[lo:lo + len(d)] = d
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cand", required=True); ap.add_argument("--out", required=True); ap.add_argument("--N", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=8); ap.add_argument("--gate_frac", type=float, default=0.10); ap.add_argument("--chunk", type=int, default=800)
    ap.add_argument("--only", nargs="*", default=None, help="restrict to family_size names, e.g. symrep_run_15")
    a = ap.parse_args()
    os.makedirs(a.out + "/_gate_cache", exist_ok=True)
    report = {}
    v2 = {}
    for n in (9, 11, 15):
        d = pd.concat(pd.read_parquet(f"{V2}grid{n}/{s}.parquet", columns=["puzzle", "solver_search_nodes", "solver_prop_fixed_frac"]) for s in ("train", "validation", "test"))
        v2[n] = d
    v2hash = {n: set(canon_hash(p) for p in v2[n].puzzle) for n in v2}
    print("v2 canonical hashes ready", {n: len(v2hash[n]) for n in v2hash}, flush=True)
    manifest = []
    combos = sorted({tuple(os.path.basename(f).rsplit("_", 2)[0:2]) for f in glob.glob(a.cand + "/*.parquet")})
    for fam_size in combos:
        fam, n = fam_size[0], int(fam_size[1]); name = f"{fam}_{n}"
        if a.only and name not in a.only: continue
        cand = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(f"{a.cand}/{fam}_{n}_*.parquet"))).sort_values("k").reset_index(drop=True)
        rep = dict(candidates=int(len(cand)))
        cand["ch"] = [canon_hash(p) for p in cand.puzzle]
        dup_v2 = cand.ch.isin(v2hash[n]); dup_self = cand.ch.duplicated(); dup_sol = cand.solution.duplicated()
        rep.update(dropped_dup_v2=int(dup_v2.sum()), dropped_dup_within=int((dup_self & ~dup_v2).sum()), dropped_dup_solution=int((dup_sol & ~dup_self & ~dup_v2).sum()))
        cand = cand[~(dup_v2 | dup_self | dup_sol)].reset_index(drop=True)
        res = []; t0 = time.time()
        with Pool(a.workers, maxtasksperchild=200) as pool:
            for c0 in range(0, len(cand), a.chunk):
                cf = f"{a.out}/_gate_cache/{name}_{c0:07d}.parquet"
                if os.path.exists(cf): g = pd.read_parquet(cf)
                else:
                    ch = cand.iloc[c0:c0 + a.chunk]
                    g = pd.DataFrame(pool.map(gate, [(int(k), p, s) for k, p, s in zip(ch.k, ch.puzzle, ch.solution)], chunksize=4))
                    g.to_parquet(cf + ".tmp"); os.replace(cf + ".tmp", cf)
                res.append(g)
                if sum(int(x.passes.sum()) for x in res) >= a.N: break
        g = pd.concat(res).reset_index(drop=True)
        rep["gated"] = int(len(g)); rep["gate_pass"] = int(g.passes.sum())
        fail = g[~g.passes]
        rep["gate_fail_reasons"] = dict(own_limit=int((fail.get("own_status", pd.Series(dtype=str)) == "limit").sum()), cpsat_limit=int((fail.get("cpsat_status", pd.Series(dtype=str)) == "limit").sum()),
                                        multiple=int((fail.get("cpsat_status", pd.Series(dtype=str)) == "multiple").sum()), other=int(len(fail)))
        keep = cand.merge(g[g.passes].drop(columns=["n_white", "n_runs", "frac_len1_runs"], errors="ignore"), on="k").head(a.N).reset_index(drop=True)
        if len(keep) == 0: report[name] = rep; print(name, "NO PUZZLES PASSED", rep, flush=True); continue
        nodes, unfixed = keep.search_nodes.values, 1 - keep.prop_fixed_frac.values
        pr = lambda x, ref: (np.searchsorted(np.sort(ref), x, "left") + np.searchsorted(np.sort(ref), x, "right")) / (2.0 * len(ref))
        keep["difficulty_score"] = (pr(nodes, nodes) + pr(unfixed, unfixed)) / 2
        q = keep.difficulty_score.quantile([1 / 3, 2 / 3]).tolist(); keep["difficulty_tertile"] = np.digitize(keep.difficulty_score, q).astype(int)
        keep["difficulty_score_v2ref"] = (pr(nodes, v2[n].solver_search_nodes.values) + pr(unfixed, 1 - v2[n].solver_prop_fixed_frac.values)) / 2
        keep["puzzle_id"] = [xxhash.xxh64(s.encode()).hexdigest() for s in keep.solution]
        keep["solver_prop_fixed_frac"] = keep.prop_fixed_frac; keep["solver_search_nodes"] = keep.search_nodes
        keep["generator_family"] = fam
        t1 = time.time(); dist = nn_audit(keep.puzzle.tolist(), v2[n].puzzle.tolist(), a.workers); L = n * n
        rep["nn_to_v2"] = dict(min_cells=int(dist.min()), min_frac=float(dist.min() / L), median_frac=float(np.median(dist) / L), within_gate=int((dist <= a.gate_frac * L).sum()))
        assert rep["nn_to_v2"]["within_gate"] == 0, f"{name}: {rep['nn_to_v2']['within_gate']} puzzles within {a.gate_frac} of a v2 puzzle"
        cols = ["puzzle", "solution", "puzzle_id", "grid_size", "generator_family", "layout", "digit_rule", "n_white", "n_runs", "frac_len1_runs", "min_run_len", "max_run_len",
                "repair_steps", "rowcol_distinct", "solver_prop_fixed_frac", "solver_search_nodes", "difficulty_score", "difficulty_tertile", "difficulty_score_v2ref"]
        keep["grid_size"] = n
        sym = []
        for pz, sl in zip(keep.puzzle, keep.solution):
            W_, d_, n_ = F.from_strings(pz, sl); sym.append(all(W_[i][j] == W_[n_ - i][n_ - j] for i in range(1, n_) for j in range(1, n_)) if fam.startswith("sym") else None)
        rep["symmetric_share"] = (float(np.mean(sym)) if fam.startswith("sym") else None)
        os.makedirs(f"{a.out}/{fam}_grid{n}", exist_ok=True)
        keep[cols].to_parquet(f"{a.out}/{fam}_grid{n}/test.parquet", index=False)
        manifest.append(keep[["puzzle_id", "generator_family", "grid_size", "k"]].assign(seed=[F.seed_for(fam, n, int(k)) for k in keep.k]))
        rep.update(kept=int(len(keep)), tertile_cuts=[float(x) for x in q], n_white_mean=float(keep.n_white.mean()), len1_runs_mean=float(keep.frac_len1_runs.mean()),
                   rowcol_distinct_share=float(keep.rowcol_distinct.mean()), repair_steps_mean=float(keep.repair_steps.mean()), search_nodes_median=float(np.median(nodes)),
                   prop_fixed_mean=float(keep.prop_fixed_frac.mean()), secs=round(time.time() - t0))
        report[name] = rep; print(name, json.dumps(rep), flush=True)
    json.dump(report, open(a.out + "/pack_report.json", "w"), indent=1)
    if manifest: pd.concat(manifest).to_parquet(a.out + "/PRIVATE_seed_manifest.parquet")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
