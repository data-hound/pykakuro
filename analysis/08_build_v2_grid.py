#!/usr/bin/env python3
"""Build the v2 split for one grid size from the independently verified-unique pool.

Policy ("minimal-change repair", so old results stay comparable):
  test_v2  = old test puzzles that are verified unique + top-up from never-released unique puzzles to 5000
  val_v2   = same for validation
  train_v2 = old train puzzles that are verified unique + top-up to 50000
Top-ups are drawn uniformly (seed 42) from verified-unique puzzles that were in no old split.
Enforced afterwards: no shared puzzle/solution/canonical-hash between splits; no near-duplicate pairs touching
val/test (pairs found by 07_canonical_dups.py are dropped from train). Component overlap is reported.
Run: python -I 08_build_v2_grid.py --size 11"""
import argparse, glob, json, os
import numpy as np, pandas as pd, xxhash
here = os.path.dirname(os.path.abspath(__file__))
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
DATA = _ROOT + "/Project/ar-diffusion-2d/data/"
ap = argparse.ArgumentParser(); ap.add_argument("--size", type=int, default=11); a = ap.parse_args()
import importlib.util as _iu
_sp = _iu.spec_from_file_location("kk_property", os.path.join(here, "kk_property.py")); kk_property = _iu.module_from_spec(_sp); _sp.loader.exec_module(kk_property)
N = {"train": 50000, "validation": 5000, "test": 5000}
pool = pd.concat(pd.read_parquet(f).drop(columns=["status"], errors="ignore") for f in sorted(glob.glob(f"{DATA}kakuro_mania/board_{a.size}_part_*.parquet")) + sorted(glob.glob(f"{DATA}kakuro_mania_gen/board_{a.size}_part_gen_*.parquet")))
c = pd.read_pickle(f"{here}/out/pool{a.size}_canon.pkl")
c["seed"] = c.seed.astype(pool.seed.dtype)
u = c.merge(pool, on="seed")
pairs = pd.read_parquet(f"{here}/out/pool{a.size}_neardup_pairs.parquet")
rng = np.random.RandomState(42)
chosen, report = {}, {"size": a.size, "pool_unique": int(len(u)), "near_dup_pairs": int(len(pairs))}
unused = u[u.old_split == "none"].sample(frac=1.0, random_state=42)
used = 0
for s in ("test", "validation", "train"):          # test first: it gets priority on the unused pool
    keep = u[u.old_split == s]
    need = N[s] - len(keep)
    top = unused.iloc[used:used + need]; used += need
    d = pd.concat([keep.assign(topped_up=False), top.assign(topped_up=True)])
    old_total = len(pd.read_parquet(f"{DATA}kakuro_kraze/grid{a.size}/{s}.parquet", columns=["puzzle"]))
    report[s] = dict(old_total=old_total, kept_verified_unique=int(len(keep)), removed_not_unique=int(old_total - len(keep)), topped_up=int(len(top)))
    chosen[s] = d
# decontamination: drop train rows that are canonical/near duplicates of val/test
held = set(chosen["test"].canon) | set(chosen["validation"].canon)
bad_train = chosen["train"].canon.isin(held)
report["train_dropped_canonical_dup_of_heldout"] = int(bad_train.sum())
ix = {p: i for i, p in enumerate(c.pid)}
heldpid = set(chosen["test"].pid) | set(chosen["validation"].pid)
nd = chosen["train"].pid.isin(set(c.pid.iloc[pairs.i.tolist() + pairs.j.tolist()])) & ~bad_train
report["train_rows_in_any_near_dup_pair"] = int(nd.sum())
assert bad_train.sum() == 0 and nd.sum() == 0, "decontamination needed - extend script before release"
for s in N: assert len(chosen[s]) == N[s], (s, len(chosen[s]))
for s in N: kk_property.assert_property(chosen[s].solution, f"v2 {s} split")
for x in ("puzzle", "solution", "canon"):
    for s1, s2 in (("train", "validation"), ("train", "test"), ("validation", "test")):
        assert not (set(chosen[s1][x]) & set(chosen[s2][x])), (x, s1, s2)
    for s in N: assert chosen[s][x].is_unique, (x, s)
out = f"{DATA}kakuro_kraze_v2/grid{a.size}"; os.makedirs(out, exist_ok=True)
cols = ["puzzle", "solution", "difficulty", "min_value", "max_value", "num_entry_squares", "is_exclusive", "puzzle_id", "grid_size"]
legacy_id = {}
for s in ("train", "validation", "test"):
    o = pd.read_parquet(f"{DATA}kakuro_kraze/grid{a.size}/{s}.parquet", columns=["puzzle", "puzzle_id"])
    legacy_id.update(dict(zip(o.puzzle, o.puzzle_id)))
mism = 0
for s, d in chosen.items():
    d = d.sample(frac=1.0, random_state=42).reset_index(drop=True)
    d["puzzle_id"] = [xxhash.xxh64(x.encode()).hexdigest() for x in d.solution]
    mism += sum(legacy_id[p] != i for p, i in zip(d.puzzle, d.puzzle_id) if p in legacy_id)
    d["grid_size"] = a.size; d["is_exclusive"] = True; d["verified_unique"] = True
    d["legacy_split"] = d.old_split; d["seed"] = d.seed
    d[cols + ["verified_unique", "legacy_split", "topped_up", "seed"]].to_parquet(f"{out}/{s}.parquet")
    chosen[s] = d
report["puzzle_id_mismatch_vs_legacy_for_kept_rows"] = int(mism)
# component overlap: share of each held-out puzzle's white cells lying in components that also occur in train
tr = {h for cs in chosen["train"].comps for h, n in cs}
bins = [(1, 1), (2, 2), (3, 5), (6, 10), (11, 999)]
for s in ("test", "validation"):
    tot = {b: 0 for b in bins}; hit = {b: 0 for b in bins}; per = []
    for cs in chosen[s].comps:
        w = sum(n for _, n in cs); h = sum(n for k, n in cs if k in tr); per.append(h / max(1, w))
        for k, n in cs:
            for b in bins:
                if b[0] <= n <= b[1]: tot[b] += n; hit[b] += n * (k in tr)
    report[f"component_overlap_{s}"] = dict(
        mean_frac_white_cells_in_train_components=float(np.mean(per)), p90=float(np.percentile(per, 90)), max=float(np.max(per)),
        by_component_size={f"{b[0]}-{b[1]}": dict(white_cells=tot[b], overlapped=hit[b], frac=(hit[b] / tot[b] if tot[b] else None)) for b in bins})
json.dump(report, open(f"{here}/out/grid{a.size}_v2_report.json", "w"), indent=2)
print(json.dumps(report, indent=2))
