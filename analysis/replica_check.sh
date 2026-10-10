#!/bin/bash
# Replica check: run the same small, deterministic jobs on any machine and print checksums of the results.
# Run on the workstation and on DCC; the two printed blocks must be identical.
#   workstation: bash replica_check.sh <python>      DCC: bash replica_check.sh <python>   (python = ardiff2d env interpreter)
set -e
PY=${1:-python}; H=$(cd "$(dirname "$0")" && pwd); T=$(mktemp -d)
$PY -I "$H/03_verify_uniqueness.py" --workers 4 --sizes 11 15 --splits test --limit 300 --data "$($PY -I -c 'import os;r="/hpc/group/tdunn/asabath/ece790_diffusion" if os.path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion";print(r+"/Project/ar-diffusion-2d/data/kakuro_kraze_v2/")')" --out "$T/u" > /dev/null
$PY -I - "$T/u" <<'P'
import sys, glob, hashlib, pandas as pd
d = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(sys.argv[1] + "/*.parquet"))).sort_values(["size", "idx"])
cols = ["size", "idx", "puzzle_id", "status", "stored_valid", "stored_is_found_solution", "n_white", "n_runs"]
print("uniqueness rows", len(d), "sha1", hashlib.sha1(d[cols].to_csv(index=False).encode()).hexdigest())
import importlib.util, os
for n in (9, 11, 15):
    root = "/hpc/group/tdunn/asabath/ece790_diffusion" if os.path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"
    x = pd.read_parquet(f"{root}/Project/ar-diffusion-2d/data/kakuro_kraze_v2/grid{n}/test.parquet")
    print("v2 grid", n, "test file content sha1", hashlib.sha1(pd.util.hash_pandas_object(x.drop(columns=[]), index=False).values.tobytes()).hexdigest())
P
rm -rf "$T"
