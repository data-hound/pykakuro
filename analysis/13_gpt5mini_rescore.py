#!/usr/bin/env python3
"""Zero-GPU, zero-API analysis of the EXISTING gpt-5-mini 11x11 outputs (kakuro-craze/results/gpt5mini_batch*):
 (a) how much did non-unique puzzles depress the reported grid accuracy? (re-scored by constraint validity, not stored solution)
 (b) does the solver-based difficulty tertile predict model failure on unique, legacy-kept puzzles? (validation of the metric)
Matches outputs to puzzles by exact puzzle text. Responses are parsed with the same row regex as data_utils.parse_grid."""
import ast, glob, json, os, re, sys, importlib.util
import numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("v03", os.path.join(here, "03_verify_uniqueness.py"))
v03 = importlib.util.module_from_spec(spec); sys.modules["v03"] = v03; spec.loader.exec_module(v03)
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
R = _ROOT + "/Project/kakuro-craze/results/"
D = _ROOT + "/Project/ar-diffusion-2d/data/"
v1 = pd.read_parquet(f"{D}kakuro_kraze/grid11/test.parquet", columns=["puzzle"]).reset_index().rename(columns={"index": "idx"})
v1["key"] = v1.puzzle.str.strip()
u = pd.concat(pd.read_parquet(f) for f in glob.glob(f"{here}/out/uniqueness/test_11_*.parquet"))[["idx", "status"]]
v1 = v1.merge(u, on="idx")
v2 = pd.read_parquet(f"{D}kakuro_kraze_v2/grid11/test.parquet")
v2["key"] = v2.puzzle.str.strip()
v1 = v1.merge(v2[["key", "difficulty_tertile", "solver_search_nodes", "topped_up"]], on="key", how="left")
rows = []
for d in ("gpt5mini_batch", "gpt5mini_batch_100TO500", "gpt5mini_batch_500TO1K", "gpt5mini_batch_1KTO5K"):
    inp = {}
    for l in open(R + d + "/batch_input.jsonl"):
        j = json.loads(l); inp[j["custom_id"]] = j["body"]["messages"][-1]["content"].split("\n", 1)[1].strip()
    for l in open(R + d + "/batch_responses.jsonl"):
        j = json.loads(l); rows.append(dict(key=inp.get(j["custom_id"]), response=j["response"], grid_correct_stored=str(j["grid_correct"]) == "True", src=d))
r = pd.DataFrame(rows).drop_duplicates("key", keep="last")
m = r.merge(v1, on="key", how="inner")
print("responses", len(r), "matched to v1 test puzzles", len(m))

def valid(puzzle, resp):
    try:
        g = v03.parse(puzzle); runs, white, _ = v03.runs_of(g)
        rows = re.findall(r"\[[^\[\]]*\]", resp)
        pg = [ast.literal_eval(x) for x in rows]
        if len(pg) != len(g): return False
        sol = {p: pg[p[0]][p[1]] for p in white}
        for t, cs in runs:
            v = [sol[p] for p in cs]
            if not all(isinstance(x, int) and 1 <= x <= 9 for x in v) or len(set(v)) != len(v) or sum(v) != t: return False
        return True
    except Exception:
        return False
m["valid"] = [valid(p, s) for p, s in zip(m.puzzle, m.response)]
m["unique"] = m.status == "unique"
def tab(df): return pd.Series(dict(n=len(df), grid_correct_vs_stored=df.grid_correct_stored.mean(), constraint_valid=df.valid.mean()))
print(m.groupby("unique").apply(tab).round(3).to_string())
print("overall stored-solution grid acc", round(m.grid_correct_stored.mean(), 3), "| overall constraint-valid", round(m.valid.mean(), 3), "| unique-only stored acc", round(m[m.unique].grid_correct_stored.mean(), 3))
mm = m[m.unique & m.difficulty_tertile.notna()]
print("\nunique legacy-kept puzzles by difficulty tertile (0 easy .. 2 hard):")
t = mm.groupby("difficulty_tertile").apply(tab).round(3); print(t.to_string())
from scipy.stats import spearmanr
rho, p = spearmanr(mm.solver_search_nodes, ~mm.valid); print("spearman(search_nodes, failure) rho=%.3f p=%.2g n=%d" % (rho, p, len(mm)))
m.drop(columns=["response", "puzzle"]).to_parquet(f"{here}/out/gpt5mini_grid11_rescored.parquet")
