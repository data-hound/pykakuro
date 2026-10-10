"""Stage A: compare the public HF dataset (Apaxdor/kakuro_kraze) with the local kakuro_kraze parquet copy.
Usage: python -I 10_compare_hf_to_local.py <download_dir>"""
import sys, json
import pandas as pd
from huggingface_hub import snapshot_download, HfApi
dl = sys.argv[1]
info = HfApi().dataset_info("Apaxdor/kakuro_kraze")
print("private", info.private, "gated", info.gated, "sha", info.sha, "lastModified", info.last_modified)
p = snapshot_download("Apaxdor/kakuro_kraze", repo_type="dataset", local_dir=dl)
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
L = _ROOT + "/Project/ar-diffusion-2d/data/kakuro_kraze/"
import glob, os
print(sorted(os.path.relpath(f, dl) for f in glob.glob(dl + "/**/*.parquet", recursive=True)))
for g in (9, 11, 15):
    for s in ("train", "validation", "test"):
        cands = glob.glob(f"{dl}/grid{g}/{s}-*.parquet") + glob.glob(f"{dl}/grid{g}/{s}.parquet") + glob.glob(f"{dl}/**/grid{g}/*{s}*.parquet", recursive=True)
        h = pd.concat(pd.read_parquet(f) for f in sorted(set(cands)))
        l = pd.read_parquet(f"{L}grid{g}/{s}.parquet")
        print(g, s, "hf", len(h), "local", len(l), "puzzle_id equal sets:", set(h.puzzle_id) == set(l.puzzle_id), "puzzle equal sets:", set(h.puzzle) == set(l.puzzle), "cols hf", list(h.columns) == list(l.columns))
