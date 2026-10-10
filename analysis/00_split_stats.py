import pandas as pd, glob, sys
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
D=_ROOT + "/Project/ar-diffusion-2d/data/"
for g in (9,11,15):
    for s in ("train","validation","test"):
        df=pd.read_parquet(f"{D}kakuro_kraze/grid{g}/{s}.parquet")
        if s=="train" and g==9: print(df.columns.tolist()); print(df.iloc[0].to_dict())
        print(g,s,len(df),"uniq_puzzle",df.puzzle.nunique(),"uniq_sol",df.solution.nunique(),"diff q",df.difficulty.quantile([0,.25,.5,.75,1]).round(2).tolist(),"nentry",df.num_entry_squares.quantile([0,.5,1]).tolist())
fs=sorted(glob.glob(D+"kakuro_mania/*.parquet")); print(len(fs))
import collections
n=collections.Counter()
for f in fs:
    df=pd.read_parquet(f,columns=["seed","is_exclusive"]); n[f.split("board_")[1].split("_part")[0]]+=len(df)
print(n)
