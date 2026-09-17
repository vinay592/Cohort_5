import argparse, csv, json, random, uuid
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent
LAND = json.loads((ROOT/"config/landscape.json").read_text(encoding="utf-8"))
OUT = None

FAILURES = [
    ("Validation","VAL_400","Required business field failed validation"),
    ("Database","DB_COMMIT_014","Transaction commit failed"),
    ("Network","NET_CONN_003","Connection reset by peer"),
    ("External Service","EXT_502","Downstream service returned 502"),
    ("Timeout","TIME_004","Downstream response exceeded SLA"),
    ("Authentication","AUTH_401","Service credential rejected"),
    ("Configuration","CFG_017","Interface configuration mismatch"),
    ("Authorization","AUTHZ_403","Caller is not authorized"),
    ("Capacity","CAP_003","Downstream service is at capacity"),
    ("Infrastructure","INFRA_008","Runtime node unavailable"),
]

SYSTEMS = {s["system_id"]: s for s in LAND["systems"]}
APPS = {}
for s in LAND["systems"]:
    for a in s["applications"]:
        APPS[(s["system_id"], a["application_id"])] = a["name"]

INTERFACES = []
for row in LAND["interfaces"]:
    iid, ss, sa, ts, ta, mw, pat, bp, crit, sla = row
    INTERFACES.append(dict(interface_id=iid, source_system=ss, source_app=sa,
                            target_system=ts, target_app=ta, middleware=mw,
                            pattern=pat, business_process=bp, criticality=crit, sla_ms=sla))

def make_event(i, start, rng):
    x = rng.choice(INTERFACES)
    roll = rng.random()
    if roll < 0.82:
        status = "SUCCESS"
        failure = None
        latency = max(20, int(rng.gauss(x["sla_ms"]*0.45, max(30,x["sla_ms"]*.10))))
    elif roll < 0.94:
        status = "RETRY"
        failure = rng.choice(FAILURES)
        latency = int(rng.uniform(x["sla_ms"]*.7, x["sla_ms"]*1.8))
    else:
        status = "FAILED"
        failure = rng.choice(FAILURES)
        latency = int(rng.uniform(x["sla_ms"]*.5, x["sla_ms"]*4.0))
    ts = start + timedelta(seconds=rng.randrange(7*24*3600))
    return {
        "event_id": f"EVT-{i:07d}",
        "interface": x["interface_id"],
        "source_system": x["source_system"],
        "source_app": APPS[(x["source_system"],x["source_app"])],
        "source_app_id": x["source_app"],
        "target_system": x["target_system"],
        "target_app": APPS[(x["target_system"],x["target_app"])],
        "target_app_id": x["target_app"],
        "middleware": x["middleware"],
        "pattern": x["pattern"],
        "business_process": x["business_process"],
        "status": status,
        "failure": failure,
        "latency": latency,
        "session": "SESS-"+uuid.uuid4().hex[:10].upper(),
        "request": "REQ-"+uuid.uuid4().hex[:12].upper(),
        "timestamp": ts,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--rows",type=int,default=6000)
    ap.add_argument("--seed",type=int,default=20260918)
    ap.add_argument("--out-dir",default=str(ROOT/"logs"))
    args=ap.parse_args()
    global OUT
    OUT=Path(args.out_dir); OUT.mkdir(parents=True,exist_ok=True)
    rng=random.Random(args.seed)
    start=datetime(2026,9,10)

    events=[make_event(i+1,start,rng) for i in range(args.rows)]

    # SAP: pipe log, field names are operational abbreviations; errors embedded in DETAILS.
    sap=[]
    for e in events:
        if e["source_system"]!="SAP_ERP": continue
        f=e["failure"]
        details=(
            f"dest={e['target_system']};app={e['source_app']};"
            f"business={e['business_process']};mw={e['middleware']};"
            f"mode={e['pattern']};err={f[1] if f else '0'};"
            f"reason={f[2] if f else 'none'};class={f[0] if f else 'none'}"
        )
        sap.append([
            e["event_id"], e["timestamp"].strftime("%d.%m.%Y %H:%M:%S"),
            e["interface"], e["source_app_id"], e["target_system"],
            {"SUCCESS":"OK","FAILED":"ERR","RETRY":"RETRY"}[e["status"]],
            e["latency"], e["session"], e["request"], details
        ])
    with open(OUT/"sap_erp.log","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f,delimiter="|")
        w.writerow(["EVT","TS_LOCAL","IFACE","APP_CODE","DEST","RESULT","ELAPSED","SESSION","CORRELATION","DETAILS"])
        w.writerows(sap)

    # Oracle: nested JSONL.
    oracle=[]
    for e in events:
        if e["source_system"]!="ORACLE_SCM": continue
        fail=e["failure"]
        oracle.append({
            "event":{"id":e["event_id"],"timestamp":e["timestamp"].isoformat()+"Z",
                     "interfaceRef":e["interface"],"businessFlow":e["business_process"]},
            "origin":{"application":e["source_app"],"system":"ORACLE_SCM"},
            "destination":{"system":e["target_system"],"application":e["target_app"]},
            "transport":{"provider":e["middleware"],"exchangePattern":e["pattern"],
                         "durationSeconds":round(e["latency"]/1000,3)},
            "trace":{"requestKey":e["request"],"sessionKey":e["session"]},
            "outcome":{"code":{"SUCCESS":"0","FAILED":"FAIL","RETRY":"RETRY"}[e["status"]]},
            "failure":None if not fail else {"category":fail[0],"code":fail[1],"message":fail[2]}
        })
    (OUT/"oracle_scm.jsonl").write_text("\n".join(json.dumps(x,separators=(",",":")) for x in oracle)+"\n",encoding="utf-8")

    # MES: fixed-width-ish key=value log with nested context packed into CONTEXT.
    mes=[]
    for e in events:
        if e["source_system"]!="MES": continue
        f=e["failure"]
        mes.append(
            f"WHEN={e['timestamp'].strftime('%Y/%m/%d %H:%M:%S')}"
            f"||TXN={e['event_id']}||FLOW={e['interface']}"
            f"||SRCAPP={e['source_app_id']}||DST={e['target_system']}"
            f"||OUT={e['status'][0]}"
            f"||DUR={e['latency']}"
            f"||SID={e['session']}||RID={e['request']}"
            f"||CONTEXT={{middleware:{e['middleware']},pattern:{e['pattern']},"
            f"bp:{e['business_process']},error:{f[1] if f else 'NA'},"
            f"message:{f[2] if f else 'NA'},root:{f[0] if f else 'NA'}}}"
        )
    (OUT/"mes_runtime.log").write_text("\n".join(mes)+"\n",encoding="utf-8")

    # PLM: XML-like event records with attributes and a failure child.
    plm=[]
    for e in events:
        if e["source_system"]!="PLM": continue
        f=e["failure"]
        failure = "" if not f else f'<failure class="{f[0]}" code="{f[1]}"><![CDATA[{f[2]}]]></failure>'
        plm.append(
            f'<event id="{e["event_id"]}" ts="{e["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ")}" '
            f'iface="{e["interface"]}" app="{e["source_app_id"]}" target="{e["target_system"]}" '
            f'channel="{e["middleware"]}" pattern="{e["pattern"]}" status="{e["status"]}" '
            f'latency="{e["latency"]}" session="{e["session"]}" request="{e["request"]}" '
            f'business="{e["business_process"]}">{failure}</event>'
        )
    (OUT/"plm_events.xml").write_text("<events>\n"+"\n".join(plm)+"\n</events>\n",encoding="utf-8")

    # CRM: semicolon-delimited audit trail with human-ish labels and error in last field.
    crm=[]
    for e in events:
        if e["source_system"]!="CRM": continue
        f=e["failure"]
        crm.append(";".join([
            e["timestamp"].strftime("%m/%d/%Y %H:%M:%S"),
            e["event_id"], e["source_app_id"], e["interface"],
            e["target_system"], e["target_app_id"], e["middleware"],
            e["pattern"], {"SUCCESS":"Completed","FAILED":"Rejected","RETRY":"Retried"}[e["status"]],
            str(e["latency"]), e["session"], e["request"],
            e["business_process"],
            (f"{f[1]}~{f[0]}~{f[2]}" if f else "")
        ]))
    (OUT/"crm_audit.txt").write_text(
        "TIME;EVENT;APP;IFACE;DEST;DEST_APP;CHANNEL;MODE;RESULT;MS;SESSION;TRACE;FLOW;FAILURE\n"
        + "\n".join(crm)+"\n",encoding="utf-8"
    )

    # HCM: CSV with different vocabulary/types and compact failure field.
    hcm=[]
    for e in events:
        if e["source_system"]!="HCM": continue
        f=e["failure"]
        hcm.append([
            e["event_id"], e["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            e["source_app_id"], e["interface"], e["target_system"],
            e["middleware"], e["pattern"], {"SUCCESS":1,"FAILED":9,"RETRY":5}[e["status"]],
            e["latency"]/1000.0, e["session"], e["request"],
            "" if not f else f"{f[1]}|{f[0]}|{f[2]}"
        ])
    with open(OUT/"hcm_activity.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f)
        w.writerow(["event_key","occurred_at","module","route_id","destination",
                    "transport","exchange","state_code","elapsed_seconds","session_ref","trace_id","fault"])
        w.writerows(hcm)

    # Interface master
    with open(OUT/"interface_master.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f)
        w.writerow(["InterfaceID","SourceSystem","SourceApplication","TargetSystem",
                    "TargetApplication","Middleware","Pattern","BusinessProcess","Criticality","SLA_ms"])
        for x in INTERFACES:
            w.writerow([x["interface_id"],x["source_system"],x["source_app"],x["target_system"],
                        x["target_app"],x["middleware"],x["pattern"],x["business_process"],
                        x["criticality"],x["sla_ms"]])

    print("Generated",len(events),"logical events across 6 systems.")
    for name in ["sap_erp.log","oracle_scm.jsonl","mes_runtime.log","plm_events.xml","crm_audit.txt","hcm_activity.csv"]:
        print(name, sum(1 for _ in open(OUT/name,encoding="utf-8")))

if __name__=="__main__":
    main()
