import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="ComplianceAI — PDF Scanner", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
  html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif}
  .stApp{background:linear-gradient(135deg,#0a0e1a 0%,#0d1530 50%,#0a1628 100%)}
  [data-testid="stSidebar"]{background:rgba(13,21,48,0.95);border-right:1px solid rgba(0,217,255,0.15)}
  .hero-header{background:linear-gradient(135deg,rgba(0,217,255,0.08),rgba(100,60,255,0.08));border:1px solid rgba(0,217,255,0.2);border-radius:16px;padding:2rem 2.5rem;margin-bottom:2rem}
  .hero-title{font-size:2.2rem;font-weight:700;background:linear-gradient(135deg,#00d9ff,#6b3fff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0}
  .hero-subtitle{color:rgba(255,255,255,0.55);font-size:0.95rem;margin-top:0.5rem}
  .section-header{font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:2px;color:rgba(0,217,255,0.7);margin-bottom:0.75rem;padding-bottom:0.5rem;border-bottom:1px solid rgba(0,217,255,0.1)}
  .metric-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:1.2rem 1.5rem;text-align:center}
  .metric-value{font-size:2rem;font-weight:700;color:#00d9ff}
  .metric-label{font-size:0.75rem;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:1px;margin-top:4px}
  .summary-banner{background:rgba(255,190,0,0.06);border:1px solid rgba(255,190,0,0.2);border-radius:12px;padding:1.2rem 1.5rem;margin:1rem 0}
  .summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:0.5rem}
  .summary-card{background:rgba(0,0,0,0.2);border-radius:10px;padding:0.9rem 1rem;text-align:center}
  .summary-val{font-size:1.5rem;font-weight:700;line-height:1}
  .summary-lbl{font-size:0.68rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px;margin-top:4px}
  .badge-pass{background:rgba(0,255,120,0.12);color:#00ff78;border:1px solid rgba(0,255,120,0.3);border-radius:20px;padding:3px 12px;font-size:0.75rem;font-weight:600}
  .badge-fail{background:rgba(255,60,60,0.12);color:#ff6b6b;border:1px solid rgba(255,60,60,0.3);border-radius:20px;padding:3px 12px;font-size:0.75rem;font-weight:600}
  .badge-warn{background:rgba(255,190,0,0.12);color:#ffbe00;border:1px solid rgba(255,190,0,0.3);border-radius:20px;padding:3px 12px;font-size:0.75rem;font-weight:600}
  .badge-rag{background:rgba(107,63,255,0.15);color:#a78bfa;border:1px solid rgba(107,63,255,0.3);border-radius:20px;padding:3px 12px;font-size:0.75rem;font-weight:600}
  .badge-skip{background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.4);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:3px 12px;font-size:0.75rem;font-weight:600}
  .sev-critical{background:rgba(180,0,0,0.2);color:#ff4444;border:1px solid rgba(255,68,68,0.4);border-radius:6px;padding:2px 10px;font-size:0.72rem;font-weight:700}
  .sev-high{background:rgba(255,107,0,0.15);color:#ff8c42;border:1px solid rgba(255,140,66,0.4);border-radius:6px;padding:2px 10px;font-size:0.72rem;font-weight:700}
  .sev-medium{background:rgba(255,190,0,0.12);color:#ffbe00;border:1px solid rgba(255,190,0,0.35);border-radius:6px;padding:2px 10px;font-size:0.72rem;font-weight:700}
  .sev-low{background:rgba(0,217,255,0.1);color:#00d9ff;border:1px solid rgba(0,217,255,0.3);border-radius:6px;padding:2px 10px;font-size:0.72rem;font-weight:700}
  .sev-none{background:rgba(0,255,120,0.08);color:#00ff78;border:1px solid rgba(0,255,120,0.2);border-radius:6px;padding:2px 10px;font-size:0.72rem;font-weight:600}
  .matrix-table{width:100%;border-collapse:collapse;margin-top:1rem}
  .matrix-table th{background:rgba(0,217,255,0.06);color:rgba(0,217,255,0.8);font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(0,217,255,0.15)}
  .matrix-table td{padding:12px 14px;border-bottom:1px solid rgba(255,255,255,0.05);vertical-align:top;font-size:0.82rem;color:rgba(255,255,255,0.75)}
  .matrix-table tr:hover td{background:rgba(255,255,255,0.02)}
  .result-card{background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:1rem 1.25rem;margin-bottom:0.75rem}
  .result-card-fail{border-left:3px solid #ff6b6b}
  .result-card-pass{border-left:3px solid #00ff78}
  .result-card-crit{border-left:3px solid #ff4444;background:rgba(180,0,0,0.06)}
  .rule-card{background:rgba(255,255,255,0.025);border:1px solid rgba(107,63,255,0.2);border-radius:10px;padding:1rem 1.25rem;margin-bottom:0.6rem}
  .violation-box{background:rgba(255,68,68,0.08);border:1px solid rgba(255,68,68,0.2);border-radius:6px;padding:6px 10px;font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#ff9090;margin-top:6px}
  .remediation-box{background:rgba(0,255,120,0.05);border:1px solid rgba(0,255,120,0.15);border-radius:6px;padding:6px 10px;font-size:0.78rem;color:rgba(0,255,120,0.8);margin-top:6px}
  .stButton>button{background:linear-gradient(135deg,#00d9ff,#6b3fff)!important;color:white!important;border:none!important;border-radius:8px!important;font-family:'Space Grotesk',sans-serif!important;font-weight:600!important;padding:0.6rem 2rem!important}
  .stProgress>div>div{background:linear-gradient(90deg,#00d9ff,#6b3fff)!important}
  .stTextArea textarea,.stTextInput input{background:rgba(255,255,255,0.04)!important;border:1px solid rgba(255,255,255,0.1)!important;color:white!important;border-radius:8px!important;font-family:'Space Grotesk',sans-serif!important}
  hr{border-color:rgba(255,255,255,0.06)!important}
  code{font-family:'JetBrains Mono',monospace!important;font-size:0.8rem!important}
</style>
""", unsafe_allow_html=True)


def severity_badge(sev):
    sev = (sev or "None").strip()
    cls = {"Critical":"sev-critical","High":"sev-high","Medium":"sev-medium","Low":"sev-low"}.get(sev,"sev-none")
    return f'<span class="{cls}">{sev}</span>'

def status_badge(status):
    s = (status or "").upper()
    if s=="PASS":  return '<span class="badge-pass">PASS</span>'
    if s=="FAIL":  return '<span class="badge-fail">FAIL</span>'
    if s=="SKIP":  return '<span class="badge-skip">SKIP</span>'
    if s=="WARN":  return '<span class="badge-warn">WARN</span>'
    return f'<span class="badge-warn">{s}</span>'

def render_summary_banner(metrics: dict, overall_status: str):
    """Render the 4-metric summary banner after each scan."""
    t  = metrics.get("time_seconds", 0)
    tk = metrics.get("total_tokens", 0)
    it = metrics.get("input_tokens", 0)
    ot = metrics.get("output_tokens", 0)
    c  = metrics.get("cost_usd", 0)
    m  = metrics.get("model", "")

    time_str  = f"{t}s"
    token_str = f"{tk:,}"
    cost_str  = f"${c:.4f}" if c >= 0.0001 else f"${c:.6f}"
    model_str = m[:22] if m else "—"

    st.markdown(f"""
    <div class="summary-banner">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <span style="color:rgba(255,190,0,0.9);font-weight:600;font-size:0.85rem;">📊 Scan Summary</span>
        <span style="color:rgba(255,255,255,0.35);font-size:0.75rem;font-family:'JetBrains Mono',monospace;">{model_str}</span>
      </div>
      <div class="summary-grid">
        <div class="summary-card">
          <div class="summary-val" style="color:#00d9ff;">{time_str}</div>
          <div class="summary-lbl">Time taken</div>
        </div>
        <div class="summary-card">
          <div class="summary-val" style="color:#a78bfa;">{token_str}</div>
          <div class="summary-lbl">Tokens used<br><span style="font-size:0.6rem;color:rgba(255,255,255,0.25);">{it:,} in · {ot:,} out</span></div>
        </div>
        <div class="summary-card">
          <div class="summary-val" style="color:#ffbe00;">{cost_str}</div>
          <div class="summary-lbl">Est. cost (USD)</div>
        </div>
        <div class="summary-card">
          <div class="summary-val" style="color:{'#ff6b6b' if overall_status=='FAILED' else '#00ff78'};">{'FAIL' if overall_status=='FAILED' else 'PASS'}</div>
          <div class="summary-lbl">Overall result</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def render_compliance_matrix(report: dict):
    controls = {k:v for k,v in report.items() if not k.startswith("_")}
    if not controls:
        st.info("No results.")
        return
    rows_html = ""
    for ctrl, data in controls.items():
        status = data.get("status","—")
        sev    = data.get("severity","None")
        pages  = data.get("flagged_pages",[])
        vtext  = data.get("violation_text","") or "—"
        explain= data.get("explanation","—")
        remed  = data.get("remediation","—")
        pages_str   = ", ".join([f"P{p}" for p in pages]) if pages else "—"
        vtext_disp  = f'<code style="color:#ff9090;font-size:0.75rem;">{vtext[:60]}{"..." if len(vtext)>60 else ""}</code>' if vtext!="—" else "—"
        rows_html += f"""<tr>
          <td style="font-weight:600;color:rgba(255,255,255,0.9);">{ctrl}</td>
          <td>{status_badge(status)}</td>
          <td>{severity_badge(sev)}</td>
          <td style="color:rgba(0,217,255,0.7);font-family:'JetBrains Mono',monospace;font-size:0.78rem;">{pages_str}</td>
          <td>{vtext_disp}</td>
          <td style="color:rgba(255,255,255,0.6);font-size:0.8rem;max-width:200px;">{explain}</td>
          <td style="color:rgba(0,255,120,0.75);font-size:0.8rem;max-width:180px;">{remed}</td>
        </tr>"""
    st.markdown(f"""<div style="overflow-x:auto;">
    <table class="matrix-table"><thead><tr>
      <th>Control</th><th>Status</th><th>Severity</th><th>Pages</th>
      <th>Violation found</th><th>Explanation</th><th>Remediation</th>
    </tr></thead><tbody>{rows_html}</tbody></table></div>""", unsafe_allow_html=True)


@st.cache_resource
def init_vector_db():
    try:
        from utils.vector_store import seed_default_rules, rebuild_faiss_from_chroma
        seed_default_rules(); rebuild_faiss_from_chroma(); return True
    except Exception as e: return str(e)

vector_db_status = init_vector_db()


def run_pipeline(uploaded_file, api_key, api_provider, model_name):
    from utils.pdf_extractor import extract_text_by_page
    from langgraph_pipeline.pipeline import build_pipeline

    progress_bar = st.progress(0, text="Initializing...")
    status_text  = st.empty()
    try:
        status_text.markdown('<p style="color:#00d9ff;font-size:0.85rem;">📄 Extracting text from PDF...</p>', unsafe_allow_html=True)
        progress_bar.progress(10, text="Extracting text...")
        pages = extract_text_by_page(uploaded_file)

        status_text.markdown('<p style="color:#a78bfa;font-size:0.85rem;">🔮 Retrieving rules from Vector DB...</p>', unsafe_allow_html=True)
        progress_bar.progress(25, text="RAG: fetching rules...")

        status_text.markdown('<p style="color:#00d9ff;font-size:0.85rem;">🔗 Building LangGraph pipeline...</p>', unsafe_allow_html=True)
        progress_bar.progress(40, text="Building pipeline...")
        pipeline = build_pipeline(api_key=api_key, provider=api_provider, model=model_name, rules_config=st.session_state.compliance_rules)

        status_text.markdown('<p style="color:#00d9ff;font-size:0.85rem;">🤖 Enterprise Compliance Auditor analyzing...</p>', unsafe_allow_html=True)
        progress_bar.progress(60, text="AI analysis running...")
        result = pipeline.invoke({"pages":pages,"filename":uploaded_file.name,"rules_config":st.session_state.compliance_rules})

        progress_bar.progress(90, text="Building compliance matrix...")
        report   = result.get("report", {})
        summary  = report.get("_summary", {})
        metrics  = summary.get("metrics", {})
        total_issues   = summary.get("failed_controls", 0)
        overall_status = "FAILED" if total_issues > 0 else "PASSED"
        highest_sev    = summary.get("highest_severity", "None")
        rules_source   = summary.get("rules_source", "Unknown")

        st.session_state.scan_history.append({
            "filename":         uploaded_file.name,
            "timestamp":        datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status":           overall_status,
            "total_issues":     total_issues,
            "highest_severity": highest_sev,
            "report":           report,
            "rules_source":     rules_source,
            "metrics":          metrics,
        })

        progress_bar.progress(100, text="Complete!")
        status_text.empty()

        st.markdown(f"""<div style="display:flex;gap:10px;align-items:center;margin-bottom:1rem;flex-wrap:wrap;">
          <span class="badge-rag">🔮 {rules_source}</span>
          {severity_badge(highest_sev)}
          <span style="color:rgba(255,255,255,0.4);font-size:0.8rem;">Highest severity</span>
        </div>""", unsafe_allow_html=True)

        if overall_status == "PASSED":
            st.success("✅ All compliance controls passed! Document is clean.")
        else:
            st.error(f"❌ {total_issues} compliance control(s) failed.")

        render_summary_banner(metrics, overall_status)

        st.markdown("### 📊 Compliance Matrix")
        render_compliance_matrix(report)

        failed_controls = {k:v for k,v in report.items() if not k.startswith("_") and v.get("status")=="FAIL"}
        if failed_controls:
            st.markdown("### 🔍 Failed Controls — Detail View")
            for ctrl_name, data in failed_controls.items():
                sev      = data.get("severity","None")
                card_cls = "result-card-crit" if sev=="Critical" else "result-card-fail"
                vtext    = data.get("violation_text","")
                remed    = data.get("remediation","")
                pages_list = data.get("flagged_pages",[])
                pages_html = "".join([f'<span style="background:rgba(255,107,107,0.15);color:#ff9090;border-radius:5px;padding:2px 8px;font-size:0.72rem;margin-right:4px;font-family:JetBrains Mono,monospace;">Page {p}</span>' for p in pages_list])
                st.markdown(f"""<div class="result-card {card_cls}">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px;">
                    <span style="color:white;font-weight:600;font-size:0.95rem;">❌ {ctrl_name}</span>
                    <div style="display:flex;gap:8px;">{severity_badge(sev)}{status_badge("FAIL")}</div>
                  </div>
                  <p style="color:rgba(255,255,255,0.65);font-size:0.82rem;margin:0 0 6px 0;">{data.get('explanation','')}</p>
                  {f'<div class="violation-box">⚠️ Violation: {vtext}</div>' if vtext else ''}
                  {f'<div class="remediation-box">✅ Remediation: {remed}</div>' if remed else ''}
                  {f'<div style="margin-top:8px;">{pages_html}</div>' if pages_list else ''}
                </div>""", unsafe_allow_html=True)

    except Exception as e:
        progress_bar.empty(); status_text.empty()
        st.error(f"Pipeline error: {str(e)}")
        st.info("Check your API key and ensure PDF contains extractable text.")


if "scan_history" not in st.session_state: st.session_state.scan_history = []
if "compliance_rules" not in st.session_state:
    st.session_state.compliance_rules = {
        "pii_check":True,"pii_description":"Flag emails, phones, Aadhaar, PAN, SSN, API keys",
        "confidential_check":True,"confidential_description":"Flag trade secrets, API keys, passwords",
        "encoding_check":True,"encoding_description":"Check UTF-8 encoding (English only)",
        "abusive_check":True,"abusive_description":"Flag abusive or unlawful content",
    }

with st.sidebar:
    st.markdown('<p style="color:#00d9ff;font-weight:700;font-size:1.1rem;letter-spacing:1px;">🛡️ ComplianceAI</p>', unsafe_allow_html=True)
    st.markdown('<p style="color:rgba(255,255,255,0.35);font-size:0.75rem;margin-top:-8px;">Enterprise Matrix + RAG + Metrics</p>', unsafe_allow_html=True)
    if vector_db_status is True: st.markdown('<span class="badge-rag">🔮 Vector DB ready</span>', unsafe_allow_html=True)
    else: st.warning(f"Vector DB: {vector_db_status}")
    st.markdown("---")
    st.markdown('<p class="section-header">Navigation</p>', unsafe_allow_html=True)
    page = st.radio("", ["📄 Scan PDF","🔮 Rule Manager (RAG)","⚙️ Check Settings","📊 Reports","📜 History"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown('<p class="section-header">API Configuration</p>', unsafe_allow_html=True)
    api_provider = st.selectbox("AI Provider", ["Groq (LLaMA 3)","Anthropic (Claude)","Google (Gemini)","OpenAI (GPT-4)"])
    api_key      = st.text_input("API Key", type="password", placeholder="Enter your API key...")
    model_map = {
        "Groq (LLaMA 3)":    ["llama-3.3-70b-versatile","llama-3.1-8b-instant"],
        "Anthropic (Claude)": ["claude-3-5-sonnet-20241022","claude-3-haiku-20240307"],
        "Google (Gemini)":    ["gemini-1.5-pro","gemini-1.5-flash"],
        "OpenAI (GPT-4)":     ["gpt-4o","gpt-4o-mini"]
    }
    model_name = st.selectbox("Model", model_map[api_provider])
    if api_key: st.success("✓ API key configured")
    st.markdown("---")
    st.markdown('<p style="color:rgba(255,255,255,0.25);font-size:0.7rem;text-align:center;">LangGraph + FAISS + ChromaDB</p>', unsafe_allow_html=True)


if page == "📄 Scan PDF":
    st.markdown("""<div class="hero-header">
      <h1 class="hero-title">Enterprise Compliance Scanner</h1>
      <p class="hero-subtitle">AI-powered compliance matrix with time tracking, token usage, and cost estimation</p>
    </div>""", unsafe_allow_html=True)
    col1, col2 = st.columns([3,2])
    scan_clicked = False
    with col1:
        st.markdown('<p class="section-header">Upload Document</p>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Drop your PDF here", type=["pdf"])
        if uploaded_file:
            file_size = len(uploaded_file.read())/1024; uploaded_file.seek(0)
            st.markdown(f"""<div class="result-card result-card-pass">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div><p style="color:white;font-weight:600;margin:0;">📄 {uploaded_file.name}</p>
                <p style="color:rgba(255,255,255,0.4);margin:0;font-size:0.8rem;">{file_size:.1f} KB</p></div>
                <span class="badge-pass">READY</span>
              </div></div>""", unsafe_allow_html=True)
            st.markdown('<span class="badge-rag">🔮 Rules from Vector DB · Token usage tracked</span>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if not api_key: st.warning("⚠️ Enter your API key in the sidebar.")
            else: scan_clicked = st.button("🚀 Run Compliance Scan", use_container_width=True)
    if uploaded_file and api_key and scan_clicked:
        run_pipeline(uploaded_file, api_key, api_provider, model_name)
    with col2:
        st.markdown('<p class="section-header">Quick Stats</p>', unsafe_allow_html=True)
        total  = len(st.session_state.scan_history)
        failed = sum(1 for s in st.session_state.scan_history if s.get("status")=="FAILED")
        passed = total - failed
        try:
            from utils.vector_store import get_all_rules_from_chroma
            rule_count = len(get_all_rules_from_chroma())
        except: rule_count = 0
        st.markdown(f"""<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:1rem;">
          <div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">Total Scans</div></div>
          <div class="metric-card"><div class="metric-value" style="color:#00ff78;">{passed}</div><div class="metric-label">Passed</div></div>
          <div class="metric-card"><div class="metric-value" style="color:#ff6b6b;">{failed}</div><div class="metric-label">Failed</div></div>
          <div class="metric-card"><div class="metric-value" style="color:#a78bfa;">{rule_count}</div><div class="metric-label">Rules in DB</div></div>
        </div>""", unsafe_allow_html=True)
        if st.session_state.scan_history:
            st.markdown('<p class="section-header">Recent Scans</p>', unsafe_allow_html=True)
            for scan in reversed(st.session_state.scan_history[-5:]):
                bc  = "badge-pass" if scan["status"]=="PASSED" else "badge-fail"
                sev = scan.get("highest_severity","")
                sh  = severity_badge(sev) if sev and sev!="None" else ""
                m   = scan.get("metrics",{})
                cost_str = f"${m.get('cost_usd',0):.4f}" if m else ""
                st.markdown(f"""<div class="result-card" style="margin-bottom:8px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                      <p style="color:rgba(255,255,255,0.85);margin:0;font-size:0.82rem;font-weight:500;">{scan['filename'][:22]}{'...' if len(scan['filename'])>22 else ''}</p>
                      <p style="color:rgba(255,255,255,0.3);margin:0;font-size:0.72rem;">{scan['timestamp']} · {cost_str}</p>
                    </div>
                    <div style="display:flex;gap:6px;align-items:center;">{sh}<span class="{bc}">{scan['status']}</span></div>
                  </div></div>""", unsafe_allow_html=True)


elif page == "🔮 Rule Manager (RAG)":
    st.markdown("""<div class="hero-header">
      <h1 class="hero-title">Rule Manager</h1>
      <p class="hero-subtitle">Add, edit, and delete compliance rules stored in Vector DB. Retrieved dynamically via RAG at scan time.</p>
    </div>""", unsafe_allow_html=True)
    try:
        from utils.vector_store import add_compliance_rule, delete_compliance_rule, get_all_rules_from_chroma
        st.markdown('<p class="section-header">Add New Rule</p>', unsafe_allow_html=True)
        c1,c2 = st.columns([3,1])
        with c1: new_rule_text = st.text_area("Rule description", placeholder='e.g. "Never allow: Aadhaar numbers, PAN cards, API keys"', height=100, key="nri")
        with c2:
            category = st.selectbox("Category",["PII","Confidential","Abusive","Encoding","Custom"],key="nc")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Add Rule", use_container_width=True):
                if new_rule_text.strip():
                    rule_id = add_compliance_rule(new_rule_text.strip(), category)
                    st.success(f"✅ Added! (ID: {rule_id})"); st.rerun()
                else: st.warning("Enter a rule description.")
        st.markdown("---")
        st.markdown('<p class="section-header">Rules in Vector DB</p>', unsafe_allow_html=True)
        all_rules = get_all_rules_from_chroma()
        if not all_rules: st.info("No rules yet.")
        else:
            cats = ["All"]+list(set(r["category"] for r in all_rules))
            fc   = st.selectbox("Filter", cats, key="fcat")
            filt = all_rules if fc=="All" else [r for r in all_rules if r["category"]==fc]
            cc   = {"PII":("rgba(0,217,255,0.1)","#00d9ff"),"Confidential":("rgba(255,190,0,0.1)","#ffbe00"),"Abusive":("rgba(255,107,107,0.1)","#ff6b6b"),"Encoding":("rgba(0,255,120,0.1)","#00ff78"),"Custom":("rgba(107,63,255,0.1)","#a78bfa")}
            for rule in filt:
                bg,col = cc.get(rule["category"],("rgba(255,255,255,0.05)","rgba(255,255,255,0.6)"))
                c1,c2 = st.columns([9,1])
                with c1:
                    st.markdown(f"""<div class="rule-card">
                      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                        <span style="background:{bg};color:{col};border-radius:20px;padding:2px 10px;font-size:0.7rem;font-weight:600;">{rule['category']}</span>
                        <span style="color:rgba(255,255,255,0.25);font-size:0.7rem;font-family:JetBrains Mono,monospace;">ID: {rule['id']}</span>
                      </div>
                      <p style="color:rgba(255,255,255,0.8);font-size:0.85rem;margin:0;">{rule['text']}</p>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"d_{rule['id']}"):
                        delete_compliance_rule(rule["id"]); st.success("Deleted."); st.rerun()
        st.markdown("---")
        st.markdown('<p class="section-header">Test RAG Retrieval</p>', unsafe_allow_html=True)
        tq = st.text_input("Paste sample text to preview which rules get retrieved:", placeholder="e.g. employee Aadhaar numbers...")
        if tq:
            from utils.vector_store import retrieve_relevant_rules
            st.code(retrieve_relevant_rules(tq, top_k=4), language="text")
    except Exception as e:
        st.error(f"Vector DB error: {str(e)}")
        st.info("Run: pip3 install faiss-cpu chromadb sentence-transformers")


elif page == "⚙️ Check Settings":
    st.markdown("""<div class="hero-header">
      <h1 class="hero-title">Check Settings</h1>
      <p class="hero-subtitle">Toggle compliance controls. Actual rules come from Vector DB.</p>
    </div>""", unsafe_allow_html=True)
    rules = st.session_state.compliance_rules
    for key,label,desc_key in [
        ("pii_check","🔍 PII & Personal Data","pii_description"),
        ("confidential_check","🔒 Confidential Information","confidential_description"),
        ("encoding_check","🔤 Encoding & Language","encoding_description"),
        ("abusive_check","🚫 Abusive & Unlawful Content","abusive_description"),
    ]:
        with st.expander(label, expanded=True):
            c1,c2 = st.columns([1,4])
            with c1: rules[key]      = st.toggle("Enable", value=rules[key], key=f"t_{key}")
            with c2: rules[desc_key] = st.text_area("Prompt hint", value=rules[desc_key], key=f"d_{key}", height=70)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Save Settings"):
        st.session_state.compliance_rules = rules; st.success("✅ Saved!")


elif page == "📊 Reports":
    st.markdown("""<div class="hero-header">
      <h1 class="hero-title">Compliance Reports</h1>
      <p class="hero-subtitle">Full matrix with severity, violations, remediation, and scan metrics</p>
    </div>""", unsafe_allow_html=True)
    if not st.session_state.scan_history:
        st.markdown("""<div style="text-align:center;padding:4rem 2rem;color:rgba(255,255,255,0.3);">
          <p style="font-size:3rem;">📭</p><p style="font-size:1.1rem;">No reports yet</p></div>""", unsafe_allow_html=True)
    else:
        for i, scan in enumerate(reversed(st.session_state.scan_history)):
            with st.expander(f"📄 {scan['filename']} — {scan['timestamp']}", expanded=(i==0)):
                sev = scan.get("highest_severity","None")
                rs  = scan.get("rules_source","")
                st.markdown(f"""<div style="display:flex;gap:10px;align-items:center;margin-bottom:1rem;flex-wrap:wrap;">
                  {status_badge(scan['status'])}{severity_badge(sev)}
                  <span class="badge-rag">🔮 {rs}</span>
                  <span style="color:rgba(255,255,255,0.35);font-size:0.8rem;">{scan['timestamp']}</span>
                </div>""", unsafe_allow_html=True)
                m = scan.get("metrics",{})
                if m: render_summary_banner(m, scan["status"])
                render_compliance_matrix(scan.get("report",{}))
                st.download_button("⬇️ Download JSON",
                    data=json.dumps(scan,indent=2,default=str),
                    file_name=f"report_{scan['filename']}.json",
                    mime="application/json", key=f"dl_{i}")


elif page == "📜 History":
    st.markdown("""<div class="hero-header">
      <h1 class="hero-title">Scan History</h1>
      <p class="hero-subtitle">All previous scans with time, cost and severity</p>
    </div>""", unsafe_allow_html=True)
    if not st.session_state.scan_history:
        st.info("No scans yet.")
    else:
        for col,hdr in zip(st.columns([2,1,1,1,1,1]),["Filename","Timestamp","Status","Severity","Cost","Time"]):
            col.markdown(f'<p style="color:rgba(255,255,255,0.4);font-size:0.72rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;">{hdr}</p>', unsafe_allow_html=True)
        st.markdown('<hr style="margin:0.5rem 0;">', unsafe_allow_html=True)
        for scan in reversed(st.session_state.scan_history):
            bc  = "badge-pass" if scan["status"]=="PASSED" else "badge-fail"
            sev = scan.get("highest_severity","None")
            m   = scan.get("metrics",{})
            cost_str = f"${m.get('cost_usd',0):.4f}" if m else "—"
            time_str = f"{m.get('time_seconds',0)}s" if m else "—"
            c1,c2,c3,c4,c5,c6 = st.columns([2,1,1,1,1,1])
            with c1: st.markdown(f'<p style="color:rgba(255,255,255,0.85);font-size:0.82rem;margin:0;padding:6px 0;">{scan["filename"][:24]}</p>', unsafe_allow_html=True)
            with c2: st.markdown(f'<p style="color:rgba(255,255,255,0.4);font-size:0.78rem;margin:0;padding:6px 0;">{scan["timestamp"]}</p>', unsafe_allow_html=True)
            with c3: st.markdown(status_badge(scan["status"]), unsafe_allow_html=True)
            with c4: st.markdown(severity_badge(sev), unsafe_allow_html=True)
            with c5: st.markdown(f'<p style="color:#ffbe00;font-size:0.82rem;margin:0;padding:6px 0;font-family:JetBrains Mono,monospace;">{cost_str}</p>', unsafe_allow_html=True)
            with c6: st.markdown(f'<p style="color:#00d9ff;font-size:0.82rem;margin:0;padding:6px 0;font-family:JetBrains Mono,monospace;">{time_str}</p>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Clear History"):
            st.session_state.scan_history = []; st.rerun()