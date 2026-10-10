#!/usr/bin/env python3
"""Merge solver metrics into the v2 parquet files and compare distributions (legacy-kept vs topped-up, old-seed vs new-seed, v1 vs v2).
Columns added: solver_prop_fixed_frac, solver_search_nodes, n_white, n_runs, frac_len1_runs, difficulty_score, difficulty_tertile (0 easy..2 hard,
within size, over the pooled v2 train+val+test); the generator's `difficulty` (timeout-capped / load-dependent) and `legacy_difficulty` are DROPPED (removed from v2 on 2026-10-09)."""
import glob, json, os
import numpy as np, pandas as pd
from scipy.stats import ks_2samp
here = os.path.dirname(os.path.abspath(__file__))
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
V2 = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_kraze_v2/"
rep = {}
for n in (9, 11, 15):
    d = pd.concat(pd.read_parquet(f) for f in glob.glob(f"{here}/out/difficulty_grid{n}/*.parquet"))
    assert len(d) == 60000 and (d.own_status == "unique").all() and d.own_matches_stored.all() and (d.block_resolve == "infeasible_ok").all(), n
    d = d.rename(columns={"prop_fixed_frac": "solver_prop_fixed_frac", "search_nodes": "solver_search_nodes"})
    d["difficulty_score"] = (d.solver_search_nodes.rank(pct=True) + (1 - d.solver_prop_fixed_frac).rank(pct=True)) / 2
    q = d.difficulty_score.quantile([1 / 3, 2 / 3]).tolist()
    d["difficulty_tertile"] = np.digitize(d.difficulty_score, q).astype(int)
    rep[n] = dict(tertile_thresholds=q, nodes_quantiles=d.solver_search_nodes.quantile([0, .25, .5, .75, .9, .99, 1]).tolist(),
                  frac_nodes_eq_1=float((d.solver_search_nodes == 1).mean()), root_solved_frac=float((d.solver_prop_fixed_frac == 1).mean()),
                  tertile_counts=d.difficulty_tertile.value_counts().sort_index().tolist())
    allv = {}
    for s in ("train", "validation", "test"):
        f = f"{V2}grid{n}/{s}.parquet"; x = pd.read_parquet(f)
        x = x.drop(columns=[c for c in ("difficulty", "legacy_difficulty") if c in x.columns])
        x = x.drop(columns=[c for c in x.columns if c in ("solver_prop_fixed_frac", "solver_search_nodes", "n_white", "n_runs", "frac_len1_runs", "difficulty_score", "difficulty_tertile")])
        m = d[d.split == s].sort_values("idx").reset_index(drop=True)
        assert len(m) == len(x)
        for c in ("solver_prop_fixed_frac", "solver_search_nodes", "n_white", "n_runs", "frac_len1_runs", "difficulty_score", "difficulty_tertile"): x[c] = m[c].values
        x.to_parquet(f); allv[s] = x
    t = allv["test"]
    feats = ["n_white", "n_runs", "frac_len1_runs", "solver_prop_fixed_frac", "solver_search_nodes", "num_entry_squares"]
    def cmp(a, b, name):
        return {name: {f: dict(mean_a=round(float(a[f].mean()), 3), mean_b=round(float(b[f].mean()), 3), ks_p=float(ks_2samp(a[f], b[f]).pvalue)) for f in feats}}
    rep[n]["test_legacykept_vs_toppedup"] = cmp(t[~t.topped_up], t[t.topped_up], "legacy_kept(a) vs topped_up(b)")
    if n == 15:
        tr = allv["train"]; tr_old = tr[tr.seed < 350000]; tr_new = tr[tr.seed >= 350000]
        rep[n]["train_oldseed_vs_newseed"] = cmp(tr_old, tr_new, "old_seed(a) vs new_seed(b)")
    # v1 sample vs v2 (v1 features from the Stage B sample files: val/test full, train 5000 sample)
    v1 = pd.concat(pd.read_parquet(f) for f in glob.glob(f"{here}/out/uniqueness/*_{n}_*.parquet"))
    v1t = v1[v1.split == "test"]
    rep[n]["test_v1_vs_v2"] = {f: dict(mean_v1=round(float(v1t[f].mean()), 3), mean_v2=round(float(t[f].mean()), 3), ks_p=float(ks_2samp(v1t[f], t[f]).pvalue)) for f in ("n_white", "n_runs", "frac_len1_runs")}
json.dump(rep, open(f"{here}/out/v2_distribution_report.json", "w"), indent=1)
for n in rep:
    r = rep[n]; print("== grid", n, "tertile counts", r["tertile_counts"], "root-solved frac", round(r["root_solved_frac"], 3), "nodes==1", round(r["frac_nodes_eq_1"], 3), "nodes q", r["nodes_quantiles"])
    for k in ("test_legacykept_vs_toppedup", "train_oldseed_vs_newseed"):
        if k in r:
            for name, fs in r[k].items(): print("  ", name, {f: (v["mean_a"], v["mean_b"], f"p={v['ks_p']:.2g}") for f, v in fs.items()})
    print("   v1 vs v2 test", {f: (v["mean_v1"], v["mean_v2"], f"p={v['ks_p']:.2g}") for f, v in r["test_v1_vs_v2"].items()})
