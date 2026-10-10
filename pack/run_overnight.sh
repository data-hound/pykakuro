#!/bin/bash
# Production generation of v3 candidates. Resumable: re-running skips finished chunks. Detached use:
#   nohup nice -n 10 bash pack/run_overnight.sh > OUT/run.log 2>&1 &
# Resource cap: 16 worker processes, backs off while load > 36 or CPU die > 75 C (see generate_pack.py).
# Seeds per (family, size) were set from the pilot yields (symrep_run 9/11/15: 43/19+/46 %, symrep_rc 9/11: 66/6 %, blob_run 48/32/11 %).
set -u
OUT=${1:?output dir}
PY=${PY:-python}
G="$PY -I $(dirname "$0")/generate_pack.py --out $OUT --workers 16 --chunk 2000"
$G --families symrep_run --sizes 9  --seeds 12000
$G --families symrep_run --sizes 11 --seeds 24000
$G --families symrep_run --sizes 15 --seeds 12000
$G --families symrep_rc  --sizes 9  --seeds 12000
$G --families symrep_rc  --sizes 11 --seeds 80000
$G --families blob_run   --sizes 9  --seeds 10000
$G --families blob_run   --sizes 11 --seeds 12000
$G --families blob_run   --sizes 15 --seeds 40000
echo ALL_DONE
