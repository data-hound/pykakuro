#!/usr/bin/env python3
"""Exact (non-probabilistic) near-duplicate audit of the v2 splits.

For every held-out puzzle we compute its EXACT nearest neighbour in the training split (brute force over all 50 000 training puzzles, no hashing, no sampling), plus
test<->validation and within-split neighbours, and a null baseline (training puzzles against the rest of training).

Distance = number of grid cells whose token differs. A cell token is: black, white, or a clue cell with its (right, down) sums, so two puzzles are close only if layout AND clue
numbers agree. The distance is the minimum over two orientations of the candidate (as is, and transposed with the clue pair swapped), i.e. symmetric duplicates are caught.
Boards are compared on their full N x N canvas (the generator anchors every board at the top-left, first row/column are clue/black).

Outputs: out/exact_nn_audit.json (summary per size and pair), out/exact_nn_audit_<size>.parquet (per held-out puzzle: nearest neighbour id and distance).
Gate: --gate_frac F (default 0.10) exits 1 if any validation/test puzzle has a training (or test<->validation) neighbour within F * cells.
Run: python -I 21_exact_nn_audit.py --sizes 9 11 15 --workers 16"""
import argparse, ast, json, os, sys, time
from multiprocessing import Pool
import numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if os.path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"
V2 = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_kraze_v2/"
BASE = 46                                           # clue sums are 0..45
_A_id = _A_T = _B = _SELF = None


def encode(puzzle):
    g = [ast.literal_eval(l.strip()) for l in puzzle.strip().splitlines() if l.strip()]
    H, W = len(g), len(g[0]); a = np.zeros((H, W), np.int16); t = np.zeros((W, H), np.int16)
    for r in range(H):
        for c in range(W):
            x = g[r][c]
            if isinstance(x, tuple): a[r, c] = 2 + x[0] * BASE + x[1]; t[c, r] = 2 + x[1] * BASE + x[0]
            elif x == 1: a[r, c] = 1; t[c, r] = 1
    return a.ravel(), t.ravel()


def encode_all(puzzles):
    e = [encode(p) for p in puzzles]
    return np.stack([x[0] for x in e]), np.stack([x[1] for x in e])


def nn_chunk(args):
    lo, hi = args
    k = hi - lo; Aid, At = _A_id[lo:hi], _A_T[lo:hi]
    d1 = np.count_nonzero(Aid[:, None, :] != _B[None, :, :], axis=2)
    d2 = np.count_nonzero(At[:, None, :] != _B[None, :, :], axis=2)
    d = np.minimum(d1, d2)
    if _SELF is not None: d[np.arange(k), _SELF[lo:hi]] = 10 ** 6          # exclude the puzzle itself
    j = d.argmin(1); r = np.arange(k)
    return lo, d[r, j], j, (d2[r, j] < d1[r, j])


def nearest(A_id, A_T, B, self_idx, workers, chunk):
    global _A_id, _A_T, _B, _SELF
    _A_id, _A_T, _B, _SELF = A_id, A_T, B, self_idx
    dist = np.zeros(len(A_id), np.int32); nn = np.zeros(len(A_id), np.int64); tr = np.zeros(len(A_id), bool)
    with Pool(workers) as p:
        for lo, d, j, t in p.imap_unordered(nn_chunk, [(i, min(i + chunk, len(A_id))) for i in range(0, len(A_id), chunk)]):
            dist[lo:lo + len(d)] = d; nn[lo:lo + len(d)] = j; tr[lo:lo + len(d)] = t
    return dist, nn, tr


def summarize(dist, L):
    f = dist / L; thr = {"0": 0, "<=1": 1, "<=2": 2, "<=1%": int(0.01 * L), "<=5%": int(0.05 * L), "<=10%": int(0.10 * L), "<=20%": int(0.20 * L)}
    return dict(n=int(len(dist)), cells=int(L), min=int(dist.min()), min_frac=float(f.min()), p1=float(np.percentile(f, 1)), median_frac=float(np.median(f)), mean_frac=float(f.mean()),
                counts_within={k: int((dist <= v).sum()) for k, v in thr.items()})


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--sizes", nargs="+", type=int, default=[9, 11, 15]); ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--chunk", type=int, default=16); ap.add_argument("--baseline_n", type=int, default=3000); ap.add_argument("--gate_frac", type=float, default=0.10); a = ap.parse_args()
    from scipy.stats import ks_2samp
    report, gate_fail = {}, False
    for n in a.sizes:
        t0 = time.time(); L = n * n
        d = {s: pd.read_parquet(f"{V2}grid{n}/{s}.parquet", columns=["puzzle_id", "puzzle"]) for s in ("train", "validation", "test")}
        enc = {s: encode_all(d[s].puzzle) for s in d}
        rep = {}; rows = []
        def run(name, src, dst, same=False, sample=None):
            Aid, At = enc[src]; idx = np.arange(len(Aid))
            if sample is not None: idx = np.random.RandomState(0).choice(len(Aid), sample, replace=False); Aid, At = Aid[idx], At[idx]
            dist, nn, tr = nearest(Aid, At, enc[dst][0], idx if same else None, a.workers, a.chunk)
            rep[name] = summarize(dist, L); rep[name]["seconds"] = round(time.time() - t0, 1)
            return dist, nn, tr, idx
        for name, src, dst, same in [("test->train", "test", "train", False), ("validation->train", "validation", "train", False),
                                     ("test->validation", "test", "validation", False), ("test->test(self excl.)", "test", "test", True), ("validation->validation(self excl.)", "validation", "validation", True)]:
            dist, nn, tr, idx = run(name, src, dst, same)
            if not same: rows.append(pd.DataFrame(dict(pair=name, puzzle_id=d[src].puzzle_id.values, nn_puzzle_id=d[dst].puzzle_id.values[nn], nn_dist=dist, nn_frac=dist / L, nn_transposed=tr)))
            if name in ("test->train", "validation->train", "test->validation") and dist.min() <= a.gate_frac * L: gate_fail = True
            if name == "test->train": test_train = dist
        dist_b, _, _, _ = run("null: train(sample)->train(self excl.)", "train", "train", True, a.baseline_n)
        rep["ks_test_vs_null_p"] = float(ks_2samp(test_train / L, dist_b / L).pvalue)
        pd.concat(rows).to_parquet(f"{here}/out/exact_nn_audit_{n}.parquet")
        report[str(n)] = rep
        c = rep["test->train"]
        print(f"grid{n} ({L} cells, {round(time.time()-t0)} s): test->train nearest neighbour: min {c['min']} cells ({100*c['min_frac']:.1f} %), 1st pct {100*c['p1']:.1f} %, median {100*c['median_frac']:.1f} %; "
              f"within 10 %: {c['counts_within']['<=10%']}, within 20 %: {c['counts_within']['<=20%']}; KS(test vs null) p = {rep['ks_test_vs_null_p']:.3g}", flush=True)
    json.dump(report, open(f"{here}/out/exact_nn_audit.json", "w"), indent=1)
    print("GATE", "FAILED: held-out puzzle within " + str(a.gate_frac) + " of a training puzzle" if gate_fail else f"passed: no validation/test puzzle is within {a.gate_frac:.0%} of cells of any training (or test<->validation) puzzle")
    sys.exit(1 if gate_fail else 0)


if __name__ == "__main__":
    main()
