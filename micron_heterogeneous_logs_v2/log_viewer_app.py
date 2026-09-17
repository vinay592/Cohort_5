import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

# Setup page
st.set_page_config(
    page_title="Heterogeneous Log Showcase",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Dark premium styling */
    .stApp { background-color: #0f172a; color: #e2e8f0; font-family: 'Inter', sans-serif; }
    .css-1d391kg { background-color: #1e293b; }
    h1, h2, h3 { color: #f8fafc; font-weight: 600; }
    .raw-box { background-color: #1e293b; border: 1px solid #334155; padding: 15px; border-radius: 8px; font-family: monospace; white-space: pre-wrap; font-size: 0.85rem; color: #a78bfa; height: 100%; overflow-x: auto; }
    .norm-box { background-color: #1e293b; border: 1px solid #334155; padding: 15px; border-radius: 8px; font-family: monospace; white-space: pre-wrap; font-size: 0.85rem; color: #34d399; height: 100%; overflow-x: auto;}
    .log-pair { margin-bottom: 2rem; border-bottom: 1px solid #334155; padding-bottom: 2rem; }
    div[data-testid="stSidebar"] { border-right: 1px solid #1e3a5f; }
</style>
""", unsafe_allow_html=True)

st.title("🔍 Heterogeneous Log Normalization Showcase")
st.markdown("Compare messy, proprietary raw logs with their cleanly converted normalized schemas.")

# Configurations
LOGS_DIR = Path("logs")
NORM_DIR = Path("normalized")

SYSTEMS = {
    "SAP ERP": {"raw": "sap_erp.log", "norm": "sap_erp_normalized.csv", "format": "Pipe-delimited text"},
    "Oracle SCM": {"raw": "oracle_scm.jsonl", "norm": "oracle_scm_normalized.csv", "format": "JSON Lines"},
    "MES": {"raw": "mes_runtime.log", "norm": "mes_runtime_normalized.csv", "format": "Double-pipe Key/Value"},
    "PLM": {"raw": "plm_events.xml", "norm": "plm_events_normalized.csv", "format": "XML Events"},
    "CRM": {"raw": "crm_audit.txt", "norm": "crm_audit_normalized.csv", "format": "Semicolon-delimited"},
    "HCM": {"raw": "hcm_activity.csv", "norm": "hcm_activity_normalized.csv", "format": "CSV with proprietary codes"},
}

# Sidebar
selected_system = st.sidebar.selectbox("Select System to Inspect", list(SYSTEMS.keys()))
sys_config = SYSTEMS[selected_system]

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Raw Format:** {sys_config['format']}")
st.sidebar.markdown(f"**Raw File:** `{sys_config['raw']}`")
st.sidebar.markdown(f"**Target File:** `{sys_config['norm']}`")
st.sidebar.markdown("---")
import xml.etree.ElementTree as ET

def parse_messy_log(system, raw_str):
    try:
        if system == "Oracle SCM":
            return json.loads(raw_str)
        elif system == "SAP ERP":
            parts = raw_str.split('|')
            if len(parts) >= 10:
                details = {}
                for kv in parts[9].split(';'):
                    if '=' in kv:
                        k, v = kv.split('=', 1)
                        details[k] = v
                return {
                    "EVT": parts[0], "TS_LOCAL": parts[1], "IFACE": parts[2], "APP_CODE": parts[3],
                    "DEST": parts[4], "RESULT": parts[5], "ELAPSED": parts[6], "SESSION": parts[7],
                    "CORRELATION": parts[8], "DETAILS": details
                }
        elif system == "MES":
            parts = raw_str.split('||')
            obj = {}
            for p in parts:
                if '=' in p:
                    k, v = p.split('=', 1)
                    if k == 'CONTEXT' and v.startswith('{') and v.endswith('}'):
                        ctx = {}
                        for kv in v[1:-1].split(','):
                            if ':' in kv:
                                ck, cv = kv.split(':', 1)
                                ctx[ck] = cv
                        obj[k] = ctx
                    else:
                        obj[k] = v
            return obj
        elif system == "PLM":
            root = ET.fromstring(raw_str)
            obj = dict(root.attrib)
            for child in root:
                obj[child.tag] = dict(child.attrib)
                if child.text:
                    obj[child.tag]["text"] = child.text
            return obj
        elif system == "CRM":
            parts = raw_str.split(';')
            headers = ["TIME", "EVENT", "APP", "IFACE", "DEST", "DEST_APP", "CHANNEL", "MODE", "RESULT", "MS", "SESSION", "TRACE", "FLOW", "FAILURE"]
            return dict(zip(headers, parts))
        elif system == "HCM":
            parts = raw_str.split(',')
            headers = ["event_key", "occurred_at", "module", "route_id", "destination", "transport", "exchange", "state_code", "elapsed_seconds", "session_ref", "trace_id", "fault"]
            return dict(zip(headers, parts))
    except Exception:
        pass
    return {"raw_content": raw_str}

# Sidebar settings
failures_only = st.sidebar.checkbox("Show Only Integration Failures", value=True)
num_events = st.sidebar.slider("Number of events to display", min_value=1, max_value=50, value=5)

# Load data
@st.cache_data
def load_data(system_key):
    cfg = SYSTEMS[system_key]
    raw_path = LOGS_DIR / cfg['raw']
    norm_path = NORM_DIR / cfg['norm']
    
    if not raw_path.exists() or not norm_path.exists():
        return [], pd.DataFrame()
        
    # Read normalized
    try:
        norm_df = pd.read_csv(norm_path)
    except Exception:
        norm_df = pd.DataFrame()
        
    # Read raw lines, extract EventID to map them
    raw_entries = []
    evt_pattern = re.compile(r"EVT-\d{7}")
    
    with open(raw_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("<events>") or line.startswith("</events>"):
                continue # Skip XML wrapper
            if "ActivityDate" in line and "ActivityID" in line:
                continue # Skip CSV header
            
            # Find Event ID
            match = evt_pattern.search(line)
            if match:
                evt_id = match.group(0)
                raw_entries.append({"event_id": evt_id, "raw": line})
                
    return raw_entries, norm_df

raw_entries, norm_df = load_data(selected_system)

if not raw_entries or norm_df.empty:
    st.error(f"Could not load data for {selected_system}. Please ensure logs and normalized files are generated.")
    st.stop()

# Display
st.subheader(f"{selected_system} — Log Comparison")

displayed = 0
for entry in raw_entries:
    if displayed >= num_events:
        break
        
    evt_id = entry["event_id"]
    raw_str = entry["raw"]
    
    # Try to find corresponding normalized row
    norm_rows = norm_df[norm_df["EventID"] == evt_id]
    if norm_rows.empty:
        continue
        
    # Fill NA values with None before converting to dict so JSON serializes properly instead of NaN
    norm_record = norm_rows.iloc[0].where(pd.notnull(norm_rows.iloc[0]), None).to_dict()
    
    # Filter for failures
    if failures_only and str(norm_record.get("Status", "")).upper() not in ["FAILED", "RETRY"]:
        continue
    
    # Parse messy string into a consistent JSON-like dictionary
    messy_dict = parse_messy_log(selected_system, raw_str)
        
    raw_display = json.dumps(messy_dict, indent=2)
    norm_display = json.dumps(norm_record, indent=2)
    
    # Render layout
    st.markdown(f"#### 🎫 {evt_id} — {norm_record.get('Status', 'UNKNOWN')}")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**Source (`{sys_config['raw']}`)**")
        st.markdown(f'<div class="raw-box">{raw_display}</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"**Target (`{sys_config['norm']}`)**")
        st.markdown(f'<div class="norm-box">{norm_display}</div>', unsafe_allow_html=True)
        
    st.markdown('<div class="log-pair"></div>', unsafe_allow_html=True)
    displayed += 1

st.success(f"Displaying {displayed} log pairs from {selected_system}.")
