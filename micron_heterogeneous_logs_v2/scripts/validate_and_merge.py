from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
COLS=["EventID","InterfaceID","SourceSystem","TargetSystem","Middleware","Pattern",
      "Status","ErrorCode","ErrorText","RootCauseClass","Latency_ms","SessionID",
      "RequestID","Timestamp"]

files=sorted((ROOT/"normalized").glob("*_normalized.csv"))
if len(files)!=6:
    raise SystemExit(f"Expected 6 normalized files, found {len(files)}")

dfs=[]
for f in files:
    d=pd.read_csv(f)
    assert d.columns.tolist()==COLS, f"{f}: wrong schema"
    assert set(d.Status.dropna()).issubset({"Success","Failed","Retry"})
    assert d.EventID.notna().all()
    assert d.InterfaceID.notna().all()
    assert pd.to_numeric(d.Latency_ms,errors="coerce").notna().all()
    dfs.append(d)
    print(f"PASS {f.name}: {len(d)} records")

all_df=pd.concat(dfs,ignore_index=True)
all_df.to_csv(ROOT/"normalized"/"events.csv",index=False)
print("\nUnified events.csv:",len(all_df),"rows")
print(all_df.groupby(["SourceSystem","Status"]).size().unstack(fill_value=0))
