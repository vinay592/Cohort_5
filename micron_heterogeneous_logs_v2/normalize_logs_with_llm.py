import argparse, json, os, re, subprocess, sys, tempfile
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
TARGET=json.loads((ROOT/"schemas/normalized_event_schema.json").read_text())
TARGET_COLS=list(TARGET.keys())

def source_schema(path):
    suf=path.suffix.lower()
    if suf==".jsonl":
        rows=[]
        with open(path,encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
                if len(rows)>=5: break
        return {"format":"JSON Lines","columns":list(rows[0].keys()) if rows else [],
                "nested_sample_shape":rows[:1]}
    if suf==".xml":
        import xml.etree.ElementTree as ET
        root=ET.parse(path).getroot()
        first=next(iter(root),None)
        return {"format":"XML","root":root.tag,
                "event_attributes":list(first.attrib.keys()) if first is not None else [],
                "child_tags":[c.tag for c in first] if first is not None else []}
    if path.name=="crm_audit.txt":
        cols=pd.read_csv(path,sep=";",nrows=0).columns.tolist()
        return {"format":"semicolon-delimited text","columns":cols}
    if path.name=="hcm_activity.csv":
        df=pd.read_csv(path,nrows=5)
        return {"format":"CSV","columns":df.columns.tolist(),"dtypes":{c:str(t) for c,t in df.dtypes.items()}}
    if path.name=="sap_erp.log":
        df=pd.read_csv(path,sep="|",nrows=5)
        return {"format":"pipe-delimited log","columns":df.columns.tolist(),"dtypes":{c:str(t) for c,t in df.dtypes.items()}}
    # MES
    with open(path,encoding="utf-8") as f:
        line=next((x.strip() for x in f if x.strip()),"")
    keys=[x.split("=",1)[0] for x in line.split("||") if "=" in x]
    return {"format":"double-pipe key/value log","keys":keys,"example":line}

def samples(path,n=8):
    suf=path.suffix.lower()
    if suf==".jsonl":
        out=[]
        with open(path,encoding="utf-8") as f:
            for line in f:
                if line.strip(): out.append(json.loads(line))
                if len(out)>=n: break
        return out
    if suf==".xml":
        return [x for x in Path(path).read_text(encoding="utf-8").splitlines() if "<event " in x][:n]
    if path.name=="crm_audit.txt":
        return Path(path).read_text(encoding="utf-8").splitlines()[:n+1]
    if path.name=="hcm_activity.csv":
        return pd.read_csv(path,nrows=n).fillna("").to_dict("records")
    if path.name=="sap_erp.log":
        return pd.read_csv(path,sep="|",nrows=n).fillna("").to_dict("records")
    return [x.strip() for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()][:n]

def prompt_for(path, master):
    template=(ROOT/"scripts/llm_prompt_template.md").read_text(encoding="utf-8")
    return (template.replace("__TARGET_SCHEMA__",json.dumps(TARGET,indent=2))
            .replace("__INTERFACE_MASTER__",master.to_csv(index=False))
            .replace("__SOURCE_SCHEMA__",json.dumps(source_schema(path),indent=2,default=str))
            .replace("__SAMPLES__",json.dumps(samples(path),indent=2,default=str)))

def extract_llm_json(raw):
    try:
        x=json.loads(raw)
        if isinstance(x,dict) and "converter_code" in x: return x
    except Exception: pass
    chunks=[]
    for line in raw.splitlines():
        try:
            x=json.loads(line)
        except Exception: continue
        for k in ("text","content","output"):
            if isinstance(x.get(k),str): chunks.append(x[k])
        if isinstance(x.get("parts"),list):
            for p in x["parts"]:
                if isinstance(p,dict) and isinstance(p.get("text"),str): chunks.append(p["text"])
    text="\n".join(chunks) or raw
    # tolerate a fenced JSON response, while still requiring the final object
    text=re.sub(r"^```(?:json)?\s*|\s*```$","",text.strip(),flags=re.S)
    m=re.search(r"\{.*\}",text,flags=re.S)
    if not m: raise ValueError("LLM did not return JSON")
    return json.loads(m.group(0))

def call_opencode(prompt, cli):
    p=subprocess.run([cli,"run","--format","json",prompt],capture_output=True,text=True,timeout=900)
    if p.returncode: raise RuntimeError(p.stderr[-5000:])
    return extract_llm_json(p.stdout)

def validate(df, master):
    if list(df.columns)!=TARGET_COLS:
        raise ValueError(f"Wrong target columns: {list(df.columns)}")
    if not df["EventID"].notna().all(): raise ValueError("Null EventID")
    if not df["InterfaceID"].notna().all(): raise ValueError("Null InterfaceID")
    if not set(df["Status"].dropna()).issubset({"Success","Failed","Retry"}):
        raise ValueError("Invalid status")
    df["Latency_ms"]=pd.to_numeric(df["Latency_ms"],errors="raise").astype("int64")
    df["Timestamp"]=pd.to_datetime(df["Timestamp"],errors="raise")
    valid=set(master["InterfaceID"])
    bad=set(df["InterfaceID"])-valid
    if bad: raise ValueError("Unknown interfaces: "+str(sorted(bad)))
    return df

# Deterministic converters are included only as an offline demo / integration test.
def offline_convert(path, master):
    if path.name=="sap_erp.log":
        d=pd.read_csv(path,sep="|",dtype=str).fillna("")
        def kv(s,k,sep=";"):
            m=re.search(rf"(?:^|{re.escape(sep)}){re.escape(k)}=([^;]*)",s)
            return m.group(1) if m else ""
        out=pd.DataFrame({
            "EventID":d.EVT,"InterfaceID":d.IFACE,"SourceSystem":"SAP_ERP",
            "TargetSystem":d.DEST,"Middleware":d.DETAILS.map(lambda x:kv(x,"mw")),
            "Pattern":d.DETAILS.map(lambda x:kv(x,"mode")),
            "Status":d.RESULT.map({"OK":"Success","ERR":"Failed","RETRY":"Retry"}),
            "ErrorCode":d.DETAILS.map(lambda x:kv(x,"err")).replace({"0":None,"":None}),
            "ErrorText":d.DETAILS.map(lambda x:kv(x,"reason")).replace({"none":None,"":None}),
            "RootCauseClass":d.DETAILS.map(lambda x:kv(x,"class")).replace({"none":None,"":None}),
            "Latency_ms":pd.to_numeric(d.ELAPSED),
            "SessionID":d.SESSION,"RequestID":d.CORRELATION,
            "Timestamp":pd.to_datetime(d.TS_LOCAL,format="%d.%m.%Y %H:%M:%S")
        })
        return out[TARGET_COLS]

    if path.name=="oracle_scm.jsonl":
        rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        im=master.set_index("InterfaceID")
        out=[]
        for x in rows:
            e=x["event"]; o=x["outcome"]; f=x.get("failure") or {}; tr=x["transport"]
            iid=e["interfaceRef"]; r=im.loc[iid]
            out.append([e["id"],iid,"ORACLE_SCM",r.TargetSystem,tr["provider"],tr["exchangePattern"],
                        {"0":"Success","FAIL":"Failed","RETRY":"Retry"}[o["code"]],
                        f.get("code"),f.get("message"),f.get("category"),
                        round(tr["durationSeconds"]*1000),x["trace"]["sessionKey"],
                        x["trace"]["requestKey"],e["timestamp"]])
        return pd.DataFrame(out,columns=TARGET_COLS)

    if path.name=="mes_runtime.log":
        rows=[]
        for line in path.read_text().splitlines():
            if not line.strip(): continue
            d={}
            for part in line.split("||"):
                if "=" in part:
                    k,v=part.split("=",1); d[k]=v
            c=d.get("CONTEXT","").strip("{}")
            def cp(k):
                m=re.search(rf"(?:^|,){re.escape(k)}:([^,}}]*)",c); return m.group(1) if m else ""
            st={"S":"Success","F":"Failed","R":"Retry"}.get(d.get("OUT"),"Failed")
            rows.append([d.get("TXN"),d.get("FLOW"),"MES",d.get("DST"),cp("middleware"),
                         cp("pattern"),st,None if cp("error") in ("","NA") else cp("error"),
                         None if cp("message") in ("","NA") else cp("message"),
                         None if cp("root") in ("","NA") else cp("root"),
                         int(d.get("DUR",0)),d.get("SID"),d.get("RID"),d.get("WHEN")])
        return pd.DataFrame(rows,columns=TARGET_COLS)

    if path.name=="plm_events.xml":
        import xml.etree.ElementTree as ET
        root=ET.parse(path).getroot()
        im=master.set_index("InterfaceID"); out=[]
        for e in root:
            iid=e.attrib["iface"]; f=next(iter(e),None); r=im.loc[iid]
            out.append([e.attrib["id"],iid,"PLM",e.attrib["target"],e.attrib["channel"],e.attrib["pattern"],
                        ({"SUCCESS":"Success","FAILED":"Failed","RETRY":"Retry"}.get(e.attrib["status"],e.attrib["status"])),f.attrib.get("code") if f is not None else None,
                        f.text if f is not None else None,f.attrib.get("class") if f is not None else None,
                        int(e.attrib["latency"]),e.attrib["session"],e.attrib["request"],e.attrib["ts"]])
        return pd.DataFrame(out,columns=TARGET_COLS)

    if path.name=="crm_audit.txt":
        d=pd.read_csv(path,sep=";",dtype=str).fillna(""); im=master.set_index("InterfaceID"); out=[]
        for _,r0 in d.iterrows():
            fail=(r0.FAILURE.split("~",2) if r0.FAILURE else [])
            out.append([r0.EVENT,r0.IFACE,"CRM",r0.DEST,r0.CHANNEL,r0.MODE,
                        {"Completed":"Success","Rejected":"Failed","Retried":"Retry"}[r0.RESULT],
                        fail[0] if fail else None,fail[2] if fail else None,fail[1] if fail else None,
                        int(r0.MS),r0.SESSION,r0.TRACE,r0.TIME])
        return pd.DataFrame(out,columns=TARGET_COLS)

    if path.name=="hcm_activity.csv":
        d=pd.read_csv(path).fillna(""); out=[]
        im=master.set_index("InterfaceID")
        for _,r in d.iterrows():
            fail=(str(r.fault).split("|",2) if r.fault else [])
            iid=r.route_id
            out.append([r.event_key,iid,"HCM",im.loc[iid].TargetSystem,r.transport,r.exchange,
                        {1:"Success",9:"Failed",5:"Retry"}[int(r.state_code)],
                        fail[0] if fail else None,fail[2] if fail else None,fail[1] if fail else None,
                        round(float(r.elapsed_seconds)*1000),r.session_ref,r.trace_id,r.occurred_at])
        return pd.DataFrame(out,columns=TARGET_COLS)
    raise ValueError(path)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input-dir",default=str(ROOT/"logs"))
    ap.add_argument("--output-dir",default=str(ROOT/"normalized"))
    ap.add_argument("--artifact-dir",default=str(ROOT/"llm_artifacts"))
    ap.add_argument("--cli",default=os.getenv("LLM_CLI","opencode"))
    ap.add_argument("--offline-demo",action="store_true")
    ap.add_argument("--execute-generated-code",action="store_true")
    args=ap.parse_args()
    inp=Path(args.input_dir); out=Path(args.output_dir); art=Path(args.artifact_dir)
    out.mkdir(parents=True,exist_ok=True); art.mkdir(parents=True,exist_ok=True)
    master=pd.read_csv(inp/"interface_master.csv",dtype=str)

    files=[inp/x for x in ["sap_erp.log","oracle_scm.jsonl","mes_runtime.log","plm_events.xml","crm_audit.txt","hcm_activity.csv"]]
    if not args.offline_demo and not args.execute_generated_code:
        raise SystemExit("LLM mode requires --execute-generated-code. Use --offline-demo to test locally.")

    for path in files:
        print("\n===",path.name,"===")
        p=prompt_for(path,master)
        if args.offline_demo:
            df=offline_convert(path,master)
            artifact={"mode":"offline-demo","note":"Deterministic converter used to validate target contract."}
        else:
            result=call_opencode(p,args.cli)
            artifact=result
            code=result.get("converter_code")
            if not isinstance(code,str): raise ValueError("Missing converter_code")
            out_file=out/(path.stem+"_normalized.csv")
            with tempfile.TemporaryDirectory(prefix="llm_converter_") as td:
                codefile=Path(td)/"converter.py"
                codefile.write_text(code,encoding="utf-8")
                env=os.environ.copy()
                env.update({"INPUT_FILE":str(path.resolve()),
                            "OUTPUT_FILE":str(out_file.resolve()),
                            "INTERFACE_MASTER":str((inp/"interface_master.csv").resolve())})
                p2=subprocess.run([sys.executable,str(codefile)],cwd=td,env=env,
                                  capture_output=True,text=True,timeout=180)
                if p2.returncode:
                    raise RuntimeError(p2.stderr[-5000:])
        if args.offline_demo:
            out_file=out/(path.stem+"_normalized.csv")
            df.to_csv(out_file,index=False)
        df=pd.read_csv(out_file)
        df=validate(df,master)
        df.to_csv(out_file,index=False)
        (art/(path.stem+"_llm_result.json")).write_text(json.dumps(artifact,indent=2,default=str),encoding="utf-8")
        print("OK:",len(df),"rows ->",out_file)

if __name__=="__main__":
    main()
