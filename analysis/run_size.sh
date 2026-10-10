#!/bin/bash
# usage: run_size.sh SIZE  (verify pool -> canonical dups -> build v2 -> re-verify written files)
set -e
S=$1
if [ "$S" != "11" ]; then /home/as1296/anaconda3/envs/ardiff2d/bin/python -I /home/as1296/dcc_mount/ece790_diffusion/Project/pykakuro/analysis/05_verify_pool.py --size $S --workers 24; fi
/home/as1296/anaconda3/envs/ardiff2d/bin/python -I /home/as1296/dcc_mount/ece790_diffusion/Project/pykakuro/analysis/06_pool_summary.py $S > /home/as1296/dcc_mount/ece790_diffusion/Project/pykakuro/analysis/out/pool${S}_summary.txt
/home/as1296/anaconda3/envs/ardiff2d/bin/python -I /home/as1296/dcc_mount/ece790_diffusion/Project/pykakuro/analysis/07_canonical_dups.py --size $S --workers 16
/home/as1296/anaconda3/envs/ardiff2d/bin/python -I /home/as1296/dcc_mount/ece790_diffusion/Project/pykakuro/analysis/08_build_v2_grid.py --size $S
/home/as1296/anaconda3/envs/ardiff2d/bin/python -I /home/as1296/dcc_mount/ece790_diffusion/Project/pykakuro/analysis/03_verify_uniqueness.py --workers 24 --sizes $S --splits train validation test --data /home/as1296/dcc_mount/ece790_diffusion/Project/ar-diffusion-2d/data/kakuro_kraze_v2/ --out /home/as1296/dcc_mount/ece790_diffusion/Project/pykakuro/analysis/out/uniqueness_v2_grid$S
