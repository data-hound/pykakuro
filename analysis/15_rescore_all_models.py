#!/usr/bin/env python3
"""Rebuttal numbers: re-score EVERY previously evaluated 11x11 run on the same v1 test data, using the independent uniqueness labels.
For each run: n matched; originally recorded grid accuracy; grid accuracy vs stored solution recomputed here; accuracy on unique vs non-unique
puzzles; constraint-valid rate (answer satisfies every run's sum/distinctness, regardless of the stored solution); parse failures;
and, on unique legacy-kept puzzles, grid accuracy by solver-difficulty tertile.
Answer extraction: text after the last </think> (whole text if none); the LAST H bracket rows (H = board height) are the answer grid.
Puzzles are matched by canonical grid text; nothing is re-run and no API/GPU is used."""
import ast, glob, json, os, re, sys, importlib.util
import numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if os.path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"
spec = importlib.util.spec_from_file_location("v03", os.path.join(here, "03_verify_uniqueness.py"))
v03 = importlib.util.module_from_spec(spec); sys.modules["v03"] = v03; spec.loader.exec_module(v03)
R = _ROOT + "/Project/kakuro-craze/results/"; D = _ROOT + "/Project/ar-diffusion-2d/data/"

def tup(x): return tuple(tup(i) if isinstance(i, list) else i for i in x) if isinstance(x, (list, tuple)) else x
def key_from_grid(g): return repr(tuple(tuple(tup(c) if isinstance(c, (list, tuple)) else c for c in row) for row in g))
def key_from_text(t): return key_from_grid([ast.literal_eval(l.strip()) for l in t.strip().splitlines() if l.strip().startswith("[")])
def find_prompt(o):
    if isinstance(o, str): return o if "Solve this Kakuro puzzle" in o else None
    if isinstance(o, dict): o = list(o.values())
    if isinstance(o, list):
        for i in o:
            r = find_prompt(i)
            if r: return r
    return None

test = pd.read_parquet(f"{D}kakuro_kraze/grid11/test.parquet", columns=["puzzle", "solution"]).reset_index().rename(columns={"index": "idx"})
test["key"] = [key_from_text(p) for p in test.puzzle]
u = pd.concat(pd.read_parquet(f) for f in glob.glob(f"{here}/out/uniqueness/test_11_*.parquet"))[["idx", "status"]]
test = test.merge(u, on="idx")
v2 = pd.read_parquet(f"{D}kakuro_kraze_v2/grid11/test.parquet", columns=["puzzle", "difficulty_tertile"])
v2["pk"] = v2.puzzle.str.strip(); test["pk"] = test.puzzle.str.strip()
test = test.merge(v2[["pk", "difficulty_tertile"]], on="pk", how="left")
assert len(test) == 5000 and test.key.is_unique

def answer_grid(resp, H):
    s = resp.split("</think>")[-1] if "</think>" in resp else resp
    rows = re.findall(r"\[[^\[\]]*\]", s)
    if len(rows) < H: return None
    try: return [ast.literal_eval(r) for r in rows[-H:]]
    except Exception: return None

def load_local(folders):   # HF-generation format: puzzle/solution/response per line
    out = []
    for d in folders:
        f = R + d + "/responses_output.jsonl"
        if not os.path.exists(f): continue
        for l in open(f):
            j = json.loads(l); p = j["puzzle"] if isinstance(j["puzzle"], list) else ast.literal_eval(j["puzzle"])
            out.append((key_from_grid(p), j["response"], str(j.get("grid_correct")) in ("1", "True")))
    return out
def load_chat(folders):    # chat-completion dicts (OpenAI-style): response["choices"][0]["message"]["content"]
    out = []
    for d in folders:
        f = R + d + "/responses_output.jsonl"
        if not os.path.exists(f): continue
        for l in open(f):
            j = json.loads(l); out.append((key_from_text(j["puzzle"]), j["response"]["choices"][0]["message"]["content"] or "", str(j.get("grid_correct")) in ("1", "True")))
    return out
def load_batch(folders):   # API batch: input prompts + responses by custom_id
    out = []
    for d in folders:
        fi, fr = R + d + "/batch_input.jsonl", R + d + "/batch_responses.jsonl"
        if not (os.path.exists(fi) and os.path.exists(fr)): continue
        inp = {}
        for l in open(fi):
            j = json.loads(l); p = find_prompt(j)
            if p: inp[j["custom_id"]] = key_from_text(p.split("\n", 1)[1])
        for l in open(fr):
            j = json.loads(l)
            if j["custom_id"] in inp: out.append((inp[j["custom_id"]], j["response"], str(j.get("grid_correct")) in ("1", "True")))
    return out

RUNS = {
 "gpt-5-mini (batch, 11x11)": (load_batch, ["gpt5mini_batch", "gpt5mini_batch_100TO500", "gpt5mini_batch_500TO1K", "gpt5mini_batch_1KTO5K"]),
 "gpt-5-nano (batch)": (load_batch, ["gpt5nano_batch"]),
 "Claude Sonnet 4.5 (batch)": (load_batch, ["claude-sonnet-4-5-20250929"]),
 "Phi-4-reasoning-plus 14B, 0-shot, 512 tok": (load_local, ["phi4reasoning_14b_batch_0TO5K"]),
 "Phi-4-reasoning-plus 14B, 1-shot, 512 tok": (load_local, ["phi4reasoning_14b_batch_0TO5K_1shot"]),
 "Phi-4-reasoning-plus 14B, 0-shot, 2000 tok": (load_local, ["phi4reasoning_14b_batch_0TO2500_16", "phi4reasoning_14b_batch_2500TO5K_16"]),
 "DeepSeek-R1-Qwen 14B, 2000 tok": (load_local, ["deepseek_r1_qwen_reasoning_14b_batch_0TO2500_16", "deepseek_r1_qwen_reasoning_14b_batch_2500TO5K_16"]),
 "Llama-3 thinking 8B, 2000 tok": (load_local, ["lamma3_thinking_8b_batch_0TO2500_16"]),
 "Mistral-Small-3.1 24B (Q8_0), 512 tok": (load_chat, ["mistral_live"]),
 "Phi-4-reasoning-plus 14B, 3-shot, 512 tok (n=100)": (load_local, ["phi4reasoning_14b_batch_0TO100_3shot"]),
}
byk = test.set_index("key")
rows, per = [], []
for name, (loader, folders) in RUNS.items():
    recs = loader(folders); seen = {}
    for k, resp, orig in recs: seen[k] = (resp, orig)      # last record per puzzle
    n_all = len(seen); res = []
    for k, (resp, orig) in seen.items():
        if k not in byk.index: continue
        t = byk.loc[k]; g = v03.parse(t.puzzle); sol = v03.parse(t.solution); runs, white, _ = v03.runs_of(g)
        ans = answer_grid(resp, len(g)); parsed = ans is not None and all(len(r) == len(g[0]) for r in ans)
        stored = valid = False
        if parsed:
            try:
                stored = all(ans[r][c] == sol[r][c] for r, c in white)
                valid = all(all(isinstance(ans[r][c], int) and 1 <= ans[r][c] <= 9 for r, c in cs) and len({ans[r][c] for r, c in cs}) == len(cs) and sum(ans[r][c] for r, c in cs) == tot for tot, cs in runs)
            except Exception: pass
        cell = 0.0
        if parsed:
            try: cell = float(np.mean([ans[r][c] == sol[r][c] for r, c in white]))   # share of white cells equal to the stored solution (0 if no complete grid)
            except Exception: cell = 0.0
        res.append(dict(run=name, idx=int(t.idx), unique=t.status == "unique", tertile=t.difficulty_tertile, parsed=parsed, stored=stored, valid=valid, orig=orig, cell=cell))
    r = pd.DataFrame(res); per.append(r)
    if r.empty: continue
    uq, nu = r[r.unique], r[~r.unique]
    tert = [f"{uq[uq.tertile == q].valid.mean():.3f}" if (uq.tertile == q).sum() else "-" for q in (0, 1, 2)]
    rows.append({"run": name, "n_matched": len(r), "orig_recorded_grid_acc": r.orig.mean(), "grid_acc_vs_stored(all)": r.stored.mean(), "n_unique": len(uq), "grid_acc_unique": uq.stored.mean(),
                 "n_nonunique": len(nu), "stored_match_nonunique": nu.stored.mean() if len(nu) else np.nan, "constraint_valid_nonunique": nu.valid.mean() if len(nu) else np.nan,
                 "constraint_valid_all": r.valid.mean(), "no_complete_grid": 1 - r.parsed.mean(), "unique_by_tertile_0/1/2": "/".join(tert)})
out = pd.DataFrame(rows)
pd.concat(per).to_parquet(f"{here}/out/rescored_all_models_per_puzzle.parquet"); out.to_csv(f"{here}/out/rescored_all_models.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
print(out.round(3).to_string(index=False))
