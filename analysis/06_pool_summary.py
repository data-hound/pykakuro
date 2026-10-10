import pandas as pd, glob, os, sys
size=sys.argv[1]
d=os.path.join(os.path.dirname(os.path.abspath(__file__)),"out",f"pool{size}")
df=pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(d+"/part_*.parquet")))
print("rows",len(df),"errors",(df.status=="error").sum(),"problems",(df.problems!="").sum(),"stored_valid",df.stored_valid.mean())
print(pd.crosstab([df.gen_is_exclusive,df.timeout_signature],df.status,margins=True))
u=df[df.status=="unique"]
print("independently unique:",len(u),"| of which gen_is_exclusive==True:",int(u.gen_is_exclusive.sum()),"| stored==found:",int(u.stored_is_found_solution.sum()))
print("gen flag True but NOT unique:",int(((df.gen_is_exclusive)&(df.status!="unique")).sum()))
