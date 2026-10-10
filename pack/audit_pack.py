#!/usr/bin/env python3
"""Duplicate and near-duplicate audit of the STAGED pack (run after build_pack.py): reads only the staged parquet files.
  (a) puzzle_id, solution and canonical-hash duplicates across ALL configs of the same grid size;
  (b) exact within-config nearest neighbour (brute force, both orientations, self excluded): min, 1st percentile, median, and the number of puzzles
      with a neighbour within 5 / 10 / 20 % of the cells. Layouts of the symmetric configs come from a small family, so close pairs are possible and are reported, not hidden.
Writes <staging>/pack_audit.json.   Run: python -I pack/audit_pack.py --staging DIR --workers 8"""
import argparse, glob, json, os, sys
from multiprocessing import Pool
import numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import build_pack as B
_A = _AT = _B = None
def chunk(rng):
    lo, hi = rng
    d1 = np.count_nonzero(B._A[lo:hi, None, :] != B._B[None, :, :], axis=2); d2 = np.count_nonzero(B._AT[lo:hi, None, :] != B._B[None, :, :], axis=2)
    d = np.minimum(d1, d2); d[np.arange(hi - lo), np.arange(lo, hi)] = 10 ** 6          # exclude self
    return lo, d.min(1)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--staging", required=True); ap.add_argument("--workers", type=int, default=8); a = ap.parse_args()
    out = {"cross_config": {}, "within_config_nn": {}}
    cfgs = sorted(glob.glob(a.staging + "/*_grid*/test.parquet")); data = {os.path.basename(os.path.dirname(f)): pd.read_parquet(f) for f in cfgs}
    for n in (9, 11, 15):
        names = [k for k in data if k.endswith(f"_grid{n}")]
        allp = pd.concat([data[k].assign(cfg=k) for k in names]); allp["ch"] = [B.canon_hash(p) for p in allp.puzzle]
        out["cross_config"][str(n)] = dict(configs=names, puzzles=int(len(allp)), dup_puzzle_id=int(allp.puzzle_id.duplicated().sum()), dup_solution=int(allp.solution.duplicated().sum()), dup_canonical=int(allp.ch.duplicated().sum()))
    for k, d in data.items():
        n = int(k.rsplit("grid", 1)[1]); L = n * n
        e = [B.encode(p) for p in d.puzzle]; B._A = np.stack([x[0] for x in e]); B._AT = np.stack([x[1] for x in e]); B._B = B._A
        dist = np.zeros(len(d), np.int32)
        with Pool(a.workers) as p:
            for lo, x in p.imap_unordered(chunk, [(i, min(i + 8, len(d))) for i in range(0, len(d), 8)]): dist[lo:lo + len(x)] = x
        f = dist / L
        out["within_config_nn"][k] = dict(n=int(len(d)), cells=L, min_cells=int(dist.min()), min_frac=float(f.min()), p1_frac=float(np.percentile(f, 1)), median_frac=float(np.median(f)),
                                          within_5pct=int((f <= .05).sum()), within_10pct=int((f <= .10).sum()), within_20pct=int((f <= .20).sum()))
        print(k, out["within_config_nn"][k], flush=True)
    json.dump(out, open(a.staging + "/pack_audit.json", "w"), indent=1); print(json.dumps(out["cross_config"]), "DONE", flush=True)
if __name__ == "__main__": main()
