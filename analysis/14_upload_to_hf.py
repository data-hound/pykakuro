#!/usr/bin/env python3
"""Upload the staged v2 dataset to Hugging Face. DRY RUN by default; nothing is sent unless --go is passed.

Steps (with --go):
  1. verify the token (whoami) and that it can write to the repo
  2. tag the CURRENT main revision as `v1` (so the old, partly non-unique data stays reachable)
  3. upload hf_staging_v2/ (README.md + kakuro_kraze/gridN/{split}.parquet) as one commit to main
  4. tag that commit `v2`
STATE-AWARE (updated 2026-10-09): v2 was already uploaded (commit 1c677bdc, tags v1 and v2). If tag v2 exists the full upload is refused; only a card update is possible:
     python 14_upload_to_hf.py --readme_only [--retag_v2] [--go]   # commit README.md only (dry run without --go); --retag_v2 moves tag v2 to that commit
Token: export HF_TOKEN=<write token> in your shell, or use a cached `huggingface-cli login` (never pass it on the command line).
Run: python 14_upload_to_hf.py --private_only  # just hide v1 now
     python 14_upload_to_hf.py            # dry run
     python 14_upload_to_hf.py --go [--then_private]   # real upload"""
import argparse, os, sys
from huggingface_hub import HfApi
REPO = "Apaxdor/kakuro_kraze"
STAGE = "/hpc/group/tdunn/asabath/ece790_diffusion/Project/ar-diffusion-2d/data/hf_staging_v2"
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
if not os.path.isdir(STAGE): STAGE = _ROOT + "/Project/ar-diffusion-2d/data/hf_staging_v2"
import importlib.util as _iu
_sp = _iu.spec_from_file_location("kk_property", _ROOT + "/Project/pykakuro/analysis/kk_property.py"); kk_property = _iu.module_from_spec(_sp); _sp.loader.exec_module(kk_property)
ap = argparse.ArgumentParser(); ap.add_argument("--go", action="store_true")
ap.add_argument("--then_private", action="store_true", help="after upload+tags, set the repo to private")
ap.add_argument("--private_only", action="store_true", help="only set the repo private (e.g. right now, before the upload)")
ap.add_argument("--readme_only", action="store_true", help="update only the dataset card (README.md) on main")
ap.add_argument("--retag_v2", action="store_true", help="with --readme_only --go: move tag v2 to the new card commit"); a = ap.parse_args()
api = HfApi(token=os.environ.get("HF_TOKEN"))
files = sorted(os.path.relpath(os.path.join(d, f), STAGE) for d, _, fs in os.walk(STAGE) for f in fs if ".cache" not in d)
print("repo", REPO, "| staging", STAGE, "| files", len(files)); [print("  ", f) for f in files]
if a.private_only:
    api.update_repo_settings(REPO, repo_type="dataset", private=True); print("repo is now private"); sys.exit(0)
import glob as _g
_n = sum(kk_property.assert_property(__import__("pandas").read_parquet(f, columns=["solution"]).solution, f) for f in sorted(_g.glob(STAGE + "/kakuro_kraze/grid*/*.parquet")))
print("row/column-wide distinct-digit property verified on all", _n, "staged puzzles")
info = api.dataset_info(REPO)
print("current main sha", info.sha, "private", info.private)
_refs = api.list_repo_refs(REPO, repo_type="dataset"); _tags = {t.name: t.target_commit for t in _refs.tags}
print("existing tags:", {k: v[:8] for k, v in _tags.items()})
if a.readme_only:
    from huggingface_hub import hf_hub_download
    _remote = open(hf_hub_download(REPO, "README.md", repo_type="dataset", revision=info.sha)).read(); _local = open(os.path.join(STAGE, "README.md")).read()
    if _remote == _local: print("card on main is already identical to the staged card; nothing to do"); sys.exit(0)
    print("staged card differs from the card on main")
    if not a.go: print("DRY RUN: would commit README.md only" + (" and move tag v2 to the new commit" if a.retag_v2 else "")); sys.exit(0)
    _c = api.upload_file(path_or_fileobj=os.path.join(STAGE, "README.md"), path_in_repo="README.md", repo_id=REPO, repo_type="dataset", commit_message="Card: state the row/column-wide distinct-digit property")
    print("committed", _c.oid)
    if a.retag_v2:
        api.delete_tag(REPO, tag="v2", repo_type="dataset"); api.create_tag(REPO, tag="v2", revision=_c.oid, repo_type="dataset", tag_message="Unique-only release (card updated)"); print("tag v2 moved to", _c.oid[:8])
    sys.exit(0)
if "v2" in _tags:
    print("v2 is ALREADY on the Hub (tag v2 ->", _tags["v2"][:8] + "). Refusing to re-tag or re-upload the dataset. To push only an updated card use --readme_only [--retag_v2] [--go]."); sys.exit(0)
assert "seed" not in __import__("pandas").read_parquet(os.path.join(STAGE, "kakuro_kraze/grid9/test.parquet")).columns or input("staged files contain `seed`; continue? [y/N] ") == "y"
if not a.go:
    print("DRY RUN: would tag", info.sha[:8], "as v1, upload the files above, tag the new commit v2."); sys.exit(0)
print("whoami:", api.whoami()["name"])
api.create_tag(REPO, tag="v1", revision=info.sha, repo_type="dataset", tag_message="Original release (contains non-unique puzzles; see v2)")
c = api.upload_folder(repo_id=REPO, repo_type="dataset", folder_path=STAGE, commit_message="v2: independently verified unique puzzles, solver-based difficulty, new card", ignore_patterns=[".cache/*"])
print("committed", c.oid)
api.create_tag(REPO, tag="v2", revision=c.oid, repo_type="dataset", tag_message="Unique-only release")
if a.then_private:
    api.update_repo_settings(REPO, repo_type="dataset", private=True); print("repo set to private")
print("done: https://huggingface.co/datasets/" + REPO)
