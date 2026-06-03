import streamlit as st
import json
from datetime import datetime

st.set_page_config(
    page_title="ComplianceAI — PDF Scanner",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
  html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
  .stApp { background: linear-gradient(135deg, #0a0e1a 0%, #0d1530 50%, #0a1628 100%); }
  [data-testid="stSidebar"] { background: rgba(13,21,48,0.95); border-right: 1px solid rgba(0,217,255,0.15); }
  .hero-header { background: linear-gradient(135deg,rgba(0,217,255,0.08),rgba(100,60,255,0.08)); border:1px solid rgba(0,217,255,0.2); border-radius:16px; padding:2rem 2.5rem; margin-bottom:2rem; }
  .hero-title { font-size:2.2rem; font-weight:700; background:linear-gradient(135deg,#00d9ff,#6b3fff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin:0; }
  .hero-subtitle { color:rgba(255,255,255,0.55); font-size:0.95rem; margin-top:0.5rem; }
  .section-header { font-size:0.7rem; font-weight:600; text-transform:uppercase; letter-spacing:2px; color:rgba(0,217,255,0.7); margin-bottom:0.75rem; padding-bottom:0.5rem; border-bottom:1px solid rgba(0,217,255,0.1); }
  .metric-card { background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:1.2rem 1.5rem; text-align:center; }
  .metric-value { font-size:2rem; font-weight:700; color:#00d9ff; }
  .metric-label { font-size:0.75rem; color:rgba(255,255,255,0.45); text-transform:uppercase; letter-spacing:1px; margin-top:4px; }
  .badge-pass { background:rgba(0,255,120,0.12); color:#00ff78; border:1px solid rgba(0,255,120,0.3); border-radius:20px; padding:3px 12px; font-size:0.75rem; font-weight:600; }
  .badge-fail { background:rgba(255,60,60,0.12); color:#ff6b6b; border:1px solid rgba(255,60,60,0.3); border-radius:20px; padding:3px 12px; font-size:0.75rem; font-weight:600; }
  .badge-warn { background:rgba(255,190,0,0.12); color:#ffbe00; border:1px solid rgba(255,190,0,0.3); border-radius:20px; padding:3px 12px; font-size:0.75rem; font-weight:600; }
  .badge-rag { background:rgba(107,63,255,0.15); color:#a78bfa; border:1px solid rgba(107,63,255,0.3); border-radius:20px; padding:3px 12px; font-size:0.75rem; font-weight:600; }
  .result-card { background:rgba(255,255,255,0.025); border:1px solid rgba(255,255,255,0.07); border-radius:10px; padding:1rem 1.25rem; margin-bottom:0.75rem; }
  .result-card-fail { border-left:3px solid #ff6b6b; }
  .result-card-pass { border-left:3px solid #00ff78; }
  .rule-card { background:rgba(255,255,255,0.025); border:1px solid rgba(107,63,255,0.2); border-radius:10px; padding:1rem 1.25rem; margin-bottom:0.6rem; }
  .stButton > button { background:linear-gradient(135deg,#00d9ff,#6b3fff) !important; color:white !important; border:none !important; border-radius:8px !important; font-family:'Space Grotesk',sans-serif !important; font-weight:600 !important; padding:0.6rem 2rem !important; }
  .stProgress > div > div { background:linear-gradient(90deg,#00d9ff,#6b3fff) !important; }
  .stTextArea textarea, .stTextInput input { background:rgba(255,255,255,0.04) !important; border:1px solid rgba(255,255,255,0.1) !important; color:white !important; border-radius:8px !important; font-family:'Space Grotesk',sans-serif !important; }
  hr { border-color:rgba(255,255,255,0.06) !important; }
  code { font-family:'JetBrains Mono',monospace !important; font-size:0.8rem !important; }
</style>
""", unsafe_allow_html=True)


# ─── Init Vector DB on startup ────────────────────────────────────────────────
@st.cache_resource
def init_vector_db():
    """Initialize Vector DB once and rebuild FAISS index."""
    try:
        from utils.vector_store import seed_default_rules, rebuild_faiss_from_chroma
        seed_default_rules()
        rebuild_faiss_from_chroma()
        return True
    except Exception as e:
        return str(e)

vector_db_status = init_vector_db()


# ─── run_pipeline ─────────────────────────────────────────────────────────────
def run_pipeline(uploaded_file, api_key, api_provider, model_name):
    from utils.pdf_extractor import extract_text_by_page
    from langgraph_pipeline.pipeline import build_pipeline

    progress_bar = st.progress(0, text="Initializing pipeline...")
    status_text  = st.empty()

    try:
        status_text.markdown('<p style="color:#00d9ff;font-size:0.85rem;">📄 Extracting text from PDF...</p>', unsafe_allow_html=True)
        progress_bar.progress(10, text="Extracting text...")
        pages = extract_text_by_page(uploaded_file)

        status_text.markdown('<p style="color:#a78bfa;font-size:0.85rem;">🔍 Retrieving compliance rules from Vector DB (RAG)...</p>', unsafe_allow_html=True)
        progress_bar.progress(25, text="RAG: fetching rules...")

        status_text.markdown('<p style="color:#00d9ff;font-size:0.85rem;">🔗 Building LangGraph pipeline...</p>', unsafe_allow_html=True)
        progress_bar.progress(40, text="Building pipeline...")

        pipeline = build_pipeline(
            api_key=api_key,
            provider=api_provider,
            model=model_name,
            rules_config=st.session_state.compliance_rules
        )

        status_text.markdown('<p style="color:#00d9ff;font-size:0.85rem;">🤖 Running AI compliance checks...</p>', unsafe_allow_html=True)
        progress_bar.progress(60, text="AI analysis running...")

        result = pipeline.invoke({
            "pages":        pages,
            "filename":     uploaded_file.name,
            "rules_config": st.session_state.compliance_rules
        })

        progress_bar.progress(90, text="Generating report...")
        report = result.get("report", {})
        total_issues = sum(1 for k, v in report.items() if k != "_summary" and v.get("status") == "FAIL")
        overall_status = "FAILED" if total_issues > 0 else "PASSED"

        st.session_state.scan_history.append({
            "filename":     uploaded_file.name,
            "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status":       overall_status,
            "total_issues": total_issues,
            "report":       report,
            "rules_source": report.get("_summary", {}).get("rules_source", "Unknown")
        })

        progress_bar.progress(100, text="Complete!")
        status_text.empty()

        rules_source = report.get("_summary", {}).get("rules_source", "")
        if rules_source:
            st.markdown(f'<span class="badge-rag">🔮 Rules source: {rules_source}</span>', unsafe_allow_html=True)

        if overall_status == "PASSED":
            st.success("✅ All compliance checks passed! Document is clean.")
        else:
            st.error(f"❌ {total_issues} compliance issue(s) detected.")

        st.markdown("### Scan Results")
        for check_name, check_result in report.items():
            if check_name == "_summary":
                continue
            is_pass = check_result.get("status") == "PASS"
            icon  = "✅" if is_pass else "❌"
            badge = '<span class="badge-pass">PASS</span>' if is_pass else '<span class="badge-fail">FAIL</span>'
            flagged = check_result.get("flagged_pages", [])
            pages_html = ""
            if flagged:
                pages_html = "<div style='margin-top:6px;'>" + "".join(
                    [f'<span style="background:rgba(255,107,107,0.15);color:#ff9090;border-radius:5px;padding:2px 8px;font-size:0.72rem;margin-right:4px;font-family:JetBrains Mono,monospace;">Page {p}</span>'
                     for p in flagged]
                ) + "</div>"

            st.markdown(f"""
            <div class="result-card {'result-card-pass' if is_pass else 'result-card-fail'}">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <span style="color:white;font-weight:600;">{icon} {check_name}</span>{badge}
              </div>
              <p style="color:rgba(255,255,255,0.6);font-size:0.82rem;margin:0;">{check_result.get('details','')}</p>
              {pages_html}
            </div>""", unsafe_allow_html=True)

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Pipeline error: {str(e)}")
        st.info("Check your API key and ensure the PDF contains extractable text.")


# ─── Session State ─────────────────────────────────────────────────────────────
if "scan_history" not in st.session_state:
    st.session_state.scan_history = []
if "compliance_rules" not in st.session_state:
    st.session_state.compliance_rules = {
        "pii_check":              True,
        "pii_description":        "Flag PII: emails, phones, Aadhaar, PAN, SSN, credit cards, API keys",
        "confidential_check":     True,
        "confidential_description": "Flag confidential business info, trade secrets, API keys, passwords",
        "encoding_check":         True,
        "encoding_description":   "Check UTF-8 encoding consistency (English only)",
        "abusive_check":          True,
        "abusive_description":    "Flag abusive, offensive, or unlawful content",
    }


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p style="color:#00d9ff;font-weight:700;font-size:1.1rem;letter-spacing:1px;">🛡️ ComplianceAI</p>', unsafe_allow_html=True)
    st.markdown('<p style="color:rgba(255,255,255,0.35);font-size:0.75rem;margin-top:-8px;">PDF Compliance Scanner + RAG</p>', unsafe_allow_html=True)

    if vector_db_status is True:
        st.markdown('<span class="badge-rag">🔮 Vector DB ready</span>', unsafe_allow_html=True)
    else:
        st.warning(f"Vector DB: {vector_db_status}")

    st.markdown("---")
    st.markdown('<p class="section-header">Navigation</p>', unsafe_allow_html=True)
    page = st.radio("", ["📄 Scan PDF", "🔮 Rule Manager (RAG)", "⚙️ Check Settings", "📊 Reports", "📜 History"], label_visibility="collapsed")

    st.markdown("---")
    st.markdown('<p class="section-header">API Configuration</p>', unsafe_allow_html=True)
    api_provider = st.selectbox("AI Provider", ["Groq (LLaMA 3)", "Anthropic (Claude)", "Google (Gemini)", "OpenAI (GPT-4)"])
    api_key      = st.text_input("API Key", type="password", placeholder="Enter your API key...")
    model_map = {
        "Groq (LLaMA 3)":    ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "Anthropic (Claude)": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
        "Google (Gemini)":    ["gemini-1.5-pro", "gemini-1.5-flash"],
        "OpenAI (GPT-4)":     ["gpt-4o", "gpt-4o-mini"]
    }
    model_name = st.selectbox("Model", model_map[api_provider])
    if api_key:
        st.success("✓ API key configured")

    st.markdown("---")
    st.markdown('<p style="color:rgba(255,255,255,0.25);font-size:0.7rem;text-align:center;">LangGraph + FAISS + ChromaDB</p>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Scan PDF
# ══════════════════════════════════════════════════════════════════════════════
if page == "📄 Scan PDF":
    st.markdown("""<div class="hero-header">
      <h1 class="hero-title">PDF Compliance Scanner</h1>
      <p class="hero-subtitle">AI-powered analysis with dynamic rules retrieved from Vector DB (RAG)</p>
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown('<p class="section-header">Upload Document</p>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Drop your PDF here", type=["pdf"])

        if uploaded_file:
            file_size = len(uploaded_file.read()) / 1024
            uploaded_file.seek(0)
            st.markdown(f"""<div class="result-card result-card-pass">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div><p style="color:white;font-weight:600;margin:0;">📄 {uploaded_file.name}</p>
                <p style="color:rgba(255,255,255,0.4);margin:0;font-size:0.8rem;">{file_size:.1f} KB · PDF</p></div>
                <span class="badge-pass">READY</span>
              </div></div>""", unsafe_allow_html=True)

            # Show RAG badge
            st.markdown('<span class="badge-rag">🔮 Rules will be retrieved from Vector DB at scan time</span>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            if not api_key:
                st.warning("⚠️ Enter your API key in the sidebar.")
            else:
                if st.button("🚀 Run Compliance Scan", use_container_width=True):
                    run_pipeline(uploaded_file, api_key, api_provider, model_name)

    with col2:
        st.markdown('<p class="section-header">Quick Stats</p>', unsafe_allow_html=True)
        total  = len(st.session_state.scan_history)
        failed = sum(1 for s in st.session_state.scan_history if s.get("status") == "FAILED")
        passed = total - failed

        # Show rule count from Vector DB
        try:
            from utils.vector_store import get_all_rules_from_chroma
            rule_count = len(get_all_rules_from_chroma())
        except Exception:
            rule_count = 0

        st.markdown(f"""<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:1rem;">
          <div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">Total Scans</div></div>
          <div class="metric-card"><div class="metric-value" style="color:#00ff78;">{passed}</div><div class="metric-label">Passed</div></div>
          <div class="metric-card"><div class="metric-value" style="color:#ff6b6b;">{failed}</div><div class="metric-label">Failed</div></div>
          <div class="metric-card"><div class="metric-value" style="color:#a78bfa;">{rule_count}</div><div class="metric-label">Rules in DB</div></div>
        </div>""", unsafe_allow_html=True)

        if st.session_state.scan_history:
            st.markdown('<p class="section-header">Recent Scans</p>', unsafe_allow_html=True)
            for scan in reversed(st.session_state.scan_history[-5:]):
                badge_class = "badge-pass" if scan["status"] == "PASSED" else "badge-fail"
                st.markdown(f"""<div class="result-card" style="margin-bottom:8px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div><p style="color:rgba(255,255,255,0.85);margin:0;font-size:0.82rem;font-weight:500;">{scan['filename'][:22]}{'...' if len(scan['filename'])>22 else ''}</p>
                    <p style="color:rgba(255,255,255,0.3);margin:0;font-size:0.72rem;">{scan['timestamp']}</p></div>
                    <span class="{badge_class}">{scan['status']}</span>
                  </div></div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Rule Manager (RAG)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔮 Rule Manager (RAG)":
    st.markdown("""<div class="hero-header">
      <h1 class="hero-title">Rule Manager</h1>
      <p class="hero-subtitle">Add, edit, and delete compliance rules stored in the Vector DB. Rules are retrieved dynamically at scan time using RAG.</p>
    </div>""", unsafe_allow_html=True)

    try:
        from utils.vector_store import (add_compliance_rule, delete_compliance_rule,
                                         get_all_rules_from_chroma)

        # ── Add New Rule ──────────────────────────────────────────────────────
        st.markdown('<p class="section-header">Add New Rule</p>', unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])
        with col1:
            new_rule_text = st.text_area(
                "Rule description",
                placeholder='e.g. "Never allow: Aadhaar numbers, PAN card numbers, API keys, employee salary data"',
                height=100,
                key="new_rule_input"
            )
        with col2:
            category = st.selectbox("Category", ["PII", "Confidential", "Abusive", "Encoding", "Custom"], key="new_cat")
            st.markdown("<br>", unsafe_allow_html=True)
            add_clicked = st.button("➕ Add Rule", use_container_width=True)

        if add_clicked:
            if new_rule_text.strip():
                rule_id = add_compliance_rule(new_rule_text.strip(), category)
                st.success(f"✅ Rule added to Vector DB! (ID: {rule_id})")
                st.rerun()
            else:
                st.warning("Please enter a rule description.")

        st.markdown("---")

        # ── Existing Rules ────────────────────────────────────────────────────
        st.markdown('<p class="section-header">Rules in Vector DB</p>', unsafe_allow_html=True)

        all_rules = get_all_rules_from_chroma()

        if not all_rules:
            st.info("No rules in Vector DB yet. Add your first rule above!")
        else:
            st.markdown(f'<p style="color:rgba(255,255,255,0.4);font-size:0.8rem;margin-bottom:1rem;">{len(all_rules)} rules stored — retrieved dynamically before each scan</p>', unsafe_allow_html=True)

            # Category filter
            categories = ["All"] + list(set(r["category"] for r in all_rules))
            filter_cat = st.selectbox("Filter by category", categories, key="filter_cat")

            filtered = all_rules if filter_cat == "All" else [r for r in all_rules if r["category"] == filter_cat]

            for rule in filtered:
                cat_colors = {
                    "PII":         ("rgba(0,217,255,0.1)",  "#00d9ff"),
                    "Confidential":("rgba(255,190,0,0.1)",  "#ffbe00"),
                    "Abusive":     ("rgba(255,107,107,0.1)","#ff6b6b"),
                    "Encoding":    ("rgba(0,255,120,0.1)",  "#00ff78"),
                    "Custom":      ("rgba(107,63,255,0.1)", "#a78bfa"),
                }
                bg, color = cat_colors.get(rule["category"], ("rgba(255,255,255,0.05)", "rgba(255,255,255,0.6)"))

                col1, col2 = st.columns([9, 1])
                with col1:
                    st.markdown(f"""<div class="rule-card">
                      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                        <span style="background:{bg};color:{color};border-radius:20px;padding:2px 10px;font-size:0.7rem;font-weight:600;">{rule['category']}</span>
                        <span style="color:rgba(255,255,255,0.25);font-size:0.7rem;font-family:JetBrains Mono,monospace;">ID: {rule['id']}</span>
                        <span style="color:rgba(255,255,255,0.2);font-size:0.7rem;">{rule.get('created_at','')[:10]}</span>
                      </div>
                      <p style="color:rgba(255,255,255,0.8);font-size:0.85rem;margin:0;line-height:1.5;">{rule['text']}</p>
                    </div>""", unsafe_allow_html=True)
                with col2:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"del_{rule['id']}", help="Delete this rule"):
                        delete_compliance_rule(rule["id"])
                        st.success(f"Rule {rule['id']} deleted.")
                        st.rerun()

        # ── RAG Preview ───────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<p class="section-header">Test RAG Retrieval</p>', unsafe_allow_html=True)
        test_query = st.text_input("Enter sample document text to see which rules get retrieved:", placeholder="e.g. This document contains employee salary information and Aadhaar numbers...")
        if test_query:
            from utils.vector_store import retrieve_relevant_rules
            retrieved = retrieve_relevant_rules(test_query, top_k=4)
            st.markdown('<p style="color:#a78bfa;font-size:0.85rem;margin-top:8px;">📋 Rules that would be injected into the AI prompt:</p>', unsafe_allow_html=True)
            st.code(retrieved, language="text")

    except Exception as e:
        st.error(f"Vector DB error: {str(e)}")
        st.info("Run: pip install faiss-cpu chromadb sentence-transformers")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Check Settings
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Check Settings":
    st.markdown("""<div class="hero-header">
      <h1 class="hero-title">Check Settings</h1>
      <p class="hero-subtitle">Toggle which compliance checks run. Fine-tune per-check prompts. Rules come from Vector DB.</p>
    </div>""", unsafe_allow_html=True)

    rules = st.session_state.compliance_rules

    with st.expander("🔍 PII Detection", expanded=True):
        c1, c2 = st.columns([1, 4])
        with c1: rules["pii_check"] = st.toggle("Enable", value=rules["pii_check"], key="pii_t")
        with c2: rules["pii_description"] = st.text_area("Prompt hint", value=rules["pii_description"], key="pii_d", height=80)

    with st.expander("🔒 Confidential Info", expanded=True):
        c1, c2 = st.columns([1, 4])
        with c1: rules["confidential_check"] = st.toggle("Enable", value=rules["confidential_check"], key="conf_t")
        with c2: rules["confidential_description"] = st.text_area("Prompt hint", value=rules["confidential_description"], key="conf_d", height=80)

    with st.expander("🔤 Encoding Check", expanded=True):
        c1, c2 = st.columns([1, 4])
        with c1: rules["encoding_check"] = st.toggle("Enable", value=rules["encoding_check"], key="enc_t")
        with c2: rules["encoding_description"] = st.text_area("Prompt hint", value=rules["encoding_description"], key="enc_d", height=80)

    with st.expander("🚫 Abusive Content", expanded=True):
        c1, c2 = st.columns([1, 4])
        with c1: rules["abusive_check"] = st.toggle("Enable", value=rules["abusive_check"], key="abu_t")
        with c2: rules["abusive_description"] = st.text_area("Prompt hint", value=rules["abusive_description"], key="abu_d", height=80)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Save Settings"):
        st.session_state.compliance_rules = rules
        st.success("✅ Settings saved!")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Reports
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Reports":
    st.markdown("""<div class="hero-header">
      <h1 class="hero-title">Compliance Reports</h1>
      <p class="hero-subtitle">Detailed AI-generated compliance analysis with page-level annotations</p>
    </div>""", unsafe_allow_html=True)

    if not st.session_state.scan_history:
        st.markdown("""<div style="text-align:center;padding:4rem 2rem;color:rgba(255,255,255,0.3);">
          <p style="font-size:3rem;">📭</p><p style="font-size:1.1rem;font-weight:500;">No reports yet</p>
          <p style="font-size:0.85rem;">Upload and scan a PDF first</p></div>""", unsafe_allow_html=True)
    else:
        for i, scan in enumerate(reversed(st.session_state.scan_history)):
            status_badge = '<span class="badge-pass">PASSED</span>' if scan["status"] == "PASSED" else '<span class="badge-fail">FAILED</span>'
            with st.expander(f"📄 {scan['filename']} — {scan['timestamp']}", expanded=(i == 0)):
                rules_src = scan.get("rules_source", "")
                st.markdown(f"""<div style="display:flex;gap:10px;align-items:center;margin-bottom:1rem;">
                  {status_badge}
                  <span class="badge-rag">🔮 {rules_src}</span>
                  <span style="color:rgba(255,255,255,0.35);font-size:0.8rem;">{scan['timestamp']}</span>
                </div>""", unsafe_allow_html=True)

                report = scan.get("report", {})
                for check_name, check_result in report.items():
                    if check_name == "_summary": continue
                    is_pass     = check_result.get("status") == "PASS"
                    card_class  = "result-card-pass" if is_pass else "result-card-fail"
                    badge_class = "badge-pass" if is_pass else "badge-fail"
                    badge_text  = "PASS" if is_pass else "FAIL"
                    flagged     = check_result.get("flagged_pages", [])
                    pages_html  = ""
                    if flagged:
                        pages_html = "<div style='margin-top:8px;'>" + "".join(
                            [f'<span style="background:rgba(255,107,107,0.15);color:#ff9090;border-radius:5px;padding:2px 8px;font-size:0.72rem;margin-right:4px;font-family:JetBrains Mono,monospace;">Page {p}</span>'
                             for p in flagged]
                        ) + "</div>"
                    st.markdown(f"""<div class="result-card {card_class}">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <span style="color:white;font-weight:600;">{check_name}</span>
                        <span class="{badge_class}">{badge_text}</span>
                      </div>
                      <p style="color:rgba(255,255,255,0.6);font-size:0.83rem;margin:0;">{check_result.get('details','')}</p>
                      {pages_html}</div>""", unsafe_allow_html=True)

                report_json = json.dumps(scan, indent=2, default=str)
                st.download_button("⬇️ Download JSON Report", data=report_json,
                                   file_name=f"report_{scan['filename']}.json",
                                   mime="application/json", key=f"dl_{i}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: History
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📜 History":
    st.markdown("""<div class="hero-header">
      <h1 class="hero-title">Scan History</h1>
      <p class="hero-subtitle">All previous compliance scans</p>
    </div>""", unsafe_allow_html=True)

    if not st.session_state.scan_history:
        st.info("No scans yet. Upload a PDF to get started!")
    else:
        for col, header in zip(st.columns([3, 2, 2, 1]), ["Filename", "Timestamp", "Status", "Issues"]):
            col.markdown(f'<p style="color:rgba(255,255,255,0.4);font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;">{header}</p>', unsafe_allow_html=True)
        st.markdown('<hr style="margin:0.5rem 0;">', unsafe_allow_html=True)

        for scan in reversed(st.session_state.scan_history):
            badge_class = "badge-pass" if scan["status"] == "PASSED" else "badge-fail"
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            with c1: st.markdown(f'<p style="color:rgba(255,255,255,0.85);font-size:0.85rem;margin:0;padding:6px 0;">{scan["filename"][:28]}</p>', unsafe_allow_html=True)
            with c2: st.markdown(f'<p style="color:rgba(255,255,255,0.45);font-size:0.8rem;margin:0;padding:6px 0;">{scan["timestamp"]}</p>', unsafe_allow_html=True)
            with c3: st.markdown(f'<span class="{badge_class}">{scan["status"]}</span>', unsafe_allow_html=True)
            with c4:
                issues = scan.get("total_issues", 0)
                color  = "#ff6b6b" if issues > 0 else "#00ff78"
                st.markdown(f'<p style="color:{color};font-weight:600;font-size:0.9rem;margin:0;padding:6px 0;">{issues}</p>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Clear History"):
            st.session_state.scan_history = []
            st.rerun()