#!/usr/bin/env python3
"""Generate candidate puzzles for the v3 expansion pack: pykakuro.families.generate over seed ranges, resumable and load-aware.

For each (family, size) the seeds seed_for(family, size, 0 .. N-1) are processed in chunks. A chunk's accepted puzzles are written to
<out>/<family>_<size>_<k0>.parquet (tmp file, then rename: the parquet is the commit marker, existing chunks are skipped on restart) and its
rejection counts to <out>/<family>_<size>_<k0>.status.json. Every seed is isolated (exceptions are recorded as status error:<Type>).
Between chunks the driver waits while the machine is busy or hot, so that it never trips the eval schedulers' own guards (launch at load 48 /
80 C, watchdog pause at 64 / 85 C).

Run: python -I pack/generate_pack.py --out DIR --families sym_rc sym_run symrep_rc symrep_run --sizes 9 11 15 --seeds 200000 --workers 16
(PYTHONPATH=src is not needed: the script puts ../src on the path.)  Accepted rows still have to pass pack/build_pack.py (full gates).
"""
import argparse, glob, json, os, sys, time
from collections import Counter
from multiprocessing import Pool
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(here) + "/src")
import logging; logging.disable(logging.CRITICAL)   # kakuro.py logs a warning when .set_cache is absent; it is not used here
import pandas as pd
from pykakuro import families as F


def cpu_temp():
    best = 0.0
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            if open(d + "/name").read().strip() == "k10temp": best = max(best, int(open(d + "/temp1_input").read()) / 1000)
        except Exception: pass
    return best


def wait_if_busy(max_load, max_cpu_c, log):
    n = 0
    while os.getloadavg()[0] > max_load or cpu_temp() > max_cpu_c:
        if n % 10 == 0: log(f"BACKOFF load={os.getloadavg()[0]:.1f} cpu={cpu_temp():.0f}C")
        n += 1; time.sleep(30)


def one(t):
    family, size, k, over = t
    t0 = time.time()
    try:
        r = F.generate(family, size, F.seed_for(family, size, k), **over)
    except Exception as e:
        r = dict(status="error:" + type(e).__name__)
    r["secs"] = time.time() - t0; r["k"] = k
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--families", nargs="+", default=list(F.FAMILIES)); ap.add_argument("--sizes", nargs="+", type=int, default=[9, 11, 15])
    ap.add_argument("--seeds", type=int, required=True, help="seeds per (family, size)"); ap.add_argument("--chunk", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=16); ap.add_argument("--max_load", type=float, default=36); ap.add_argument("--max_cpu_c", type=float, default=75)
    ap.add_argument("--set", nargs="*", default=[], help="generator overrides key=value (p, max_run, bias, repair, det_limit ...)")
    a = ap.parse_args()
    over = {}
    for kv in a.set:
        k, v = kv.split("="); over[k] = float(v) if "." in v else int(v)
    os.makedirs(a.out, exist_ok=True)
    logf = open(a.out + "/driver.log", "a")
    def log(m): logf.write(time.strftime("%F %T ") + m + "\n"); logf.flush(); print(m, flush=True)
    log(f"START families={a.families} sizes={a.sizes} seeds={a.seeds} workers={a.workers} over={over} guard load<={a.max_load} cpu<={a.max_cpu_c}C")
    with Pool(a.workers, maxtasksperchild=300) as pool:
        for fam in a.families:
            for size in a.sizes:
                for k0 in range(0, a.seeds, a.chunk):
                    fn = f"{a.out}/{fam}_{size}_{k0:07d}"
                    if os.path.exists(fn + ".parquet"): continue
                    wait_if_busy(a.max_load, a.max_cpu_c, log)
                    ks = range(k0, min(k0 + a.chunk, a.seeds)); t0 = time.time()
                    rows = list(pool.imap_unordered(one, [(fam, size, k, over) for k in ks], chunksize=10))
                    st = Counter(r["status"] for r in rows); ok = [r for r in rows if r["status"] == "ok"]
                    json.dump(dict(family=fam, size=size, k0=k0, tried=len(rows), status=dict(st), secs_total=sum(r["secs"] for r in rows), wall=time.time() - t0, over=over),
                              open(fn + ".status.json", "w"))
                    df = pd.DataFrame([dict(k=r["k"], puzzle=r["puzzle"], solution=r["solution"], **r["meta"]) for r in ok])
                    df.to_parquet(fn + ".parquet.tmp"); os.replace(fn + ".parquet.tmp", fn + ".parquet")
                    log(f"{fam} {size} k0={k0} tried={len(rows)} ok={len(ok)} {dict(st)} wall={time.time() - t0:.0f}s")
    log("DONE")


if __name__ == "__main__":
    main()
