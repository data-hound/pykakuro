import pandas as pd, glob, os
d=os.path.join(os.path.dirname(os.path.abspath(__file__)),"out","uniqueness")
df=pd.concat(pd.read_parquet(f) for f in glob.glob(d+"/*.parquet"))
print("rows",len(df),"errors",(df.status=="error").sum(),"problems",(df.problems!="").sum(),"stored_valid",df.stored_valid.mean())
t=df.groupby(["split","size","timeout_signature"]).status.value_counts().unstack(fill_value=0)
t["n"]=t.sum(axis=1); print(t.to_string())
g=df.groupby(["split","size"]).agg(n=("status","size"),pct_unique=("status",lambda s:(s=="unique").mean()*100),pct_multiple=("status",lambda s:(s=="multiple").mean()*100),pct_limit=("status",lambda s:(s=="limit").mean()*100),pct_stored_is_the_unique=("stored_is_found_solution","mean"),len1_run_frac=("frac_len1_runs","mean"))
g["pct_stored_is_the_unique"]*=100; print(g.round(2).to_string())
print("timeout-signature vs non-unique crosstab:"); print(pd.crosstab(df.timeout_signature,df.status))
