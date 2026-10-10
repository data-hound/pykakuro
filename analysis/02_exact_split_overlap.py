import pandas as pd
_ROOT = "/hpc/group/tdunn/asabath/ece790_diffusion" if __import__("os").path.isdir("/hpc/group/tdunn/asabath/ece790_diffusion") else "/home/as1296/dcc_mount/ece790_diffusion"  # same storage: DCC path, or its sshfs mount on the workstation
D=_ROOT + "/Project/ar-diffusion-2d/data/kakuro_kraze/"
for g in (9,11,15):
    s={x:set(pd.read_parquet(f"{D}grid{g}/{x}.parquet",columns=["puzzle"]).puzzle) for x in("train","validation","test")}
    print(g,"train∩val",len(s["train"]&s["validation"]),"train∩test",len(s["train"]&s["test"]),"val∩test",len(s["validation"]&s["test"]))
