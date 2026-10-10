import pandas as pd, math
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
D=_ROOT + "/Project/ar-diffusion-2d/data/kakuro_kraze/"
cap=0.05*math.log(5*10**5)
for g in (9,11,15):
    df=pd.read_parquet(f"{D}grid{g}/test.parquet")
    capped=(df.difficulty-(cap+0.01*df.num_entry_squares)).abs()<1e-6
    print(g,"timeout-signature fraction",capped.mean().round(3),"| median difficulty capped/uncapped",df.difficulty[capped].median() if capped.any() else None, df.difficulty[~capped].median())
