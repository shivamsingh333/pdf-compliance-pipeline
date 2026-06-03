import streamlit as st
import os
import json
from datetime import datetime
from pathlib import Path

st.set_page_config(
    page_title="ComplianceAI — PDF Scanner",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
  }

  .main { background: #0a0e1a; }

  .stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1530 50%, #0a1628 100%);
  }

  [data-testid="stSidebar"] {
    background: rgba(13, 21, 48, 0.95);
    border-right: 1px solid rgba(0, 217, 255, 0.15);
  }

  .hero-header {
    background: linear-gradient(135deg, rgba(0,217,255,0.08) 0%, rgba(100,60,255,0.08) 100%);
    border: 1px solid rgba(0, 217, 255, 0.2);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
  }

  .hero-title {
    font-size: 2.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #00d9ff, #6b3fff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    line-height: 1.2;
  }

  .hero-subtitle {
    color: rgba(255,255,255,0.55);
    font-size: 0.95rem;
    margin-top: 0.5rem;
    font-weight: 300;
    letter-spacing: 0.3px;
  }

  .metric-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    text-align: center;
  }

  .metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #00d9ff;
  }

  .metric-label {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.45);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 4px;
  }

  .badge-pass {
    background: rgba(0, 255, 120, 0.12);
    color: #00ff78;
    border: 1px solid rgba(0, 255, 120, 0.3);
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.5px;
  }

  .badge-fail {
    background: rgba(255, 60, 60, 0.12);
    color: #ff6b6b;
    border: 1px solid rgba(255, 60, 60, 0.3);
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.5px;
  }

  .badge-warn {
    background: rgba(255, 190, 0, 0.12);
    color: #ffbe00;
    border: 1px solid rgba(255, 190, 0, 0.3);
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.5px;
  }

  [data-testid="stFileUploader"] {
    background: rgba(0, 217, 255, 0.03);
    border: 2px dashed rgba(0, 217, 255, 0.25);
    border-radius: 12px;
    padding: 1rem;
  }

  .stButton > button {
    background: linear-gradient(135deg, #00d9ff, #6b3fff) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 2rem !important;
    transition: all 0.2s ease !important;
  }

  .stProgress > div > div {
    background: linear-gradient(90deg, #00d9ff, #6b3fff) !important;
  }

  .streamlit-expanderHeader {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
    color: rgba(255,255,255,0.8) !important;
  }

  .section-header {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: rgba(0, 217, 255, 0.7);
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(0, 217, 255, 0.1);
  }

  .result-card {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
  }

  .result-card-fail {
    border-left: 3px solid #ff6b6b;
  }

  .result-card-pass {
    border-left: 3px solid #00ff78;
  }

  hr { border-color: rgba(255,255,255,0.06) !important; }

  .stTextArea textarea, .stTextInput input {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: white !important;
    border-radius: 8px !important;
    font-family: 'Space Grotesk', sans-serif !important;
  }

  code {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
  }
</style>
""", unsafe_allow_html=True)


# ─── run_pipeline function (defined BEFORE it is called) ──────────────────────
def run_pipeline(uploaded_file, api_key, api_provider, model_name):
    from utils.pdf_extractor import extract_text_by_page
    from langgraph_pipeline.pipeline import build_pipeline

    progress_bar = st.progress(0, text="Initializing pipeline...")
    status_text = st.empty()

    try:
        status_text.markdown('<p style="color:#00d9ff; font-size:0.85rem;">📄 Extracting text from PDF...</p>', unsafe_allow_html=True)
        progress_bar.progress(15, text="Extracting text...")
        pages = extract_text_by_page(uploaded_file)

        status_text.markdown('<p style="color:#00d9ff; font-size:0.85rem;">🔗 Building LangGraph pipeline...</p>', unsafe_allow_html=True)
        progress_bar.progress(35, text="Building pipeline...")

        pipeline = build_pipeline(
            api_key=api_key,
            provider=api_provider,
            model=model_name,
            rules=st.session_state.compliance_rules
        )

        status_text.markdown('<p style="color:#00d9ff; font-size:0.85rem;">🤖 Running AI compliance analysis...</p>', unsafe_allow_html=True)
        progress_bar.progress(60, text="AI analysis running...")

        result = pipeline.invoke({
            "pages": pages,
            "filename": uploaded_file.name,
            "rules": st.session_state.compliance_rules
        })

        progress_bar.progress(90, text="Generating report...")
        status_text.markdown('<p style="color:#00d9ff; font-size:0.85rem;">📊 Generating compliance report...</p>', unsafe_allow_html=True)

        report = result.get("report", {})
        total_issues = sum(1 for k, v in report.items() if k != "_summary" and v.get("status") == "FAIL")
        overall_status = "FAILED" if total_issues > 0 else "PASSED"

        scan_entry = {
            "filename": uploaded_file.name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": overall_status,
            "total_issues": total_issues,
            "report": report
        }
        st.session_state.scan_history.append(scan_entry)

        progress_bar.progress(100, text="Complete!")
        status_text.empty()

        if overall_status == "PASSED":
            st.success("✅ All compliance checks passed! Document is clean.")
        else:
            st.error(f"❌ {total_issues} compliance issue(s) detected. See Reports for details.")

        st.markdown("### Scan Results")
        for check_name, check_result in report.items():
            if check_name == "_summary":
                continue
            is_pass = check_result.get("status") == "PASS"
            icon = "✅" if is_pass else "❌"
            badge = '<span class="badge-pass">PASS</span>' if is_pass else '<span class="badge-fail">FAIL</span>'
            st.markdown(f"""
            <div class="result-card {'result-card-pass' if is_pass else 'result-card-fail'}">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="color:white; font-weight:600;">{icon} {check_name}</span>
                {badge}
              </div>
              <p style="color:rgba(255,255,255,0.6); font-size:0.82rem; margin:0;">{check_result.get('details', '')}</p>
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Pipeline error: {str(e)}")
        st.info("Tip: Make sure your API key is valid and the PDF contains extractable text.")


# ─── Session State ─────────────────────────────────────────────────────────────
if "scan_history" not in st.session_state:
    st.session_state.scan_history = []
if "compliance_rules" not in st.session_state:
    st.session_state.compliance_rules = {
        "pii_check": True,
        "pii_description": "Flag PII: email addresses, phone numbers, SSN, credit card numbers",
        "confidential_check": True,
        "confidential_description": "Flag confidential business info: trade secrets, internal financials, IP details",
        "encoding_check": True,
        "encoding_description": "Check UTF-8 encoding consistency (English only)",
        "abusive_check": True,
        "abusive_description": "Flag abusive, offensive, or unlawful content",
    }

# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p style="color: #00d9ff; font-weight:700; font-size:1.1rem; letter-spacing:1px;">🛡️ ComplianceAI</p>', unsafe_allow_html=True)
    st.markdown('<p style="color:rgba(255,255,255,0.35); font-size:0.75rem; margin-top:-8px;">PDF Compliance Scanner</p>', unsafe_allow_html=True)
    st.markdown("---")

    st.markdown('<p class="section-header">Navigation</p>', unsafe_allow_html=True)
    page = st.radio(
        "",
        ["📄 Scan PDF", "⚙️ Compliance Rules", "📊 Reports", "📜 History"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown('<p class="section-header">API Configuration</p>', unsafe_allow_html=True)
    api_provider = st.selectbox(
        "AI Provider",
        ["Groq (LLaMA 3)", "Anthropic (Claude)", "Google (Gemini)", "OpenAI (GPT-4)"],
    )

    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder="Enter your API key...",
    )

    model_map = {
        "Groq (LLaMA 3)": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "meta-llama/llama-4-scout-17b-16e-instruct"],
        "Anthropic (Claude)": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
        "Google (Gemini)": ["gemini-1.5-pro", "gemini-1.5-flash"],
        "OpenAI (GPT-4)": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
    }
    model_name = st.selectbox("Model", model_map[api_provider])

    if api_key:
        st.success("✓ API key configured")

    st.markdown("---")
    st.markdown('<p style="color:rgba(255,255,255,0.25); font-size:0.7rem; text-align:center;">Built with LangGraph + Streamlit</p>', unsafe_allow_html=True)


# ─── Page: Scan PDF ────────────────────────────────────────────────────────────
if page == "📄 Scan PDF":
    st.markdown("""
    <div class="hero-header">
      <h1 class="hero-title">PDF Compliance Scanner</h1>
      <p class="hero-subtitle">AI-powered document analysis for PII, confidential data, encoding & content compliance</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown('<p class="section-header">Upload Document</p>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Drop your PDF here",
            type=["pdf"],
        )

        if uploaded_file:
            file_size = len(uploaded_file.read()) / 1024
            uploaded_file.seek(0)

            st.markdown(f"""
            <div class="result-card result-card-pass">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                  <p style="color:white; font-weight:600; margin:0; font-size:0.95rem;">📄 {uploaded_file.name}</p>
                  <p style="color:rgba(255,255,255,0.4); margin:0; font-size:0.8rem; margin-top:4px;">{file_size:.1f} KB · PDF Document</p>
                </div>
                <span class="badge-pass">READY</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown('<p class="section-header" style="margin-top:1.5rem;">Active Compliance Checks</p>', unsafe_allow_html=True)
            rules = st.session_state.compliance_rules
            checks_enabled = []
            if rules["pii_check"]: checks_enabled.append("🔍 PII Detection")
            if rules["confidential_check"]: checks_enabled.append("🔒 Confidential Info")
            if rules["encoding_check"]: checks_enabled.append("🔤 UTF-8 Encoding")
            if rules["abusive_check"]: checks_enabled.append("🚫 Abusive Content")

            cols = st.columns(2)
            for i, check in enumerate(checks_enabled):
                with cols[i % 2]:
                    st.markdown(f'<div class="result-card" style="padding:0.6rem 1rem;"><span style="color:rgba(0,217,255,0.9); font-size:0.85rem;">{check}</span></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            if not api_key:
                st.warning("⚠️ Please enter your API key in the sidebar to run analysis.")
            else:
                if st.button("🚀 Run Compliance Scan", use_container_width=True):
                    run_pipeline(uploaded_file, api_key, api_provider, model_name)

    with col2:
        st.markdown('<p class="section-header">Quick Stats</p>', unsafe_allow_html=True)
        total = len(st.session_state.scan_history)
        failed = sum(1 for s in st.session_state.scan_history if s.get("status") == "FAILED")
        passed = total - failed

        st.markdown(f"""
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:1rem;">
          <div class="metric-card">
            <div class="metric-value">{total}</div>
            <div class="metric-label">Total Scans</div>
          </div>
          <div class="metric-card">
            <div class="metric-value" style="color: #00ff78;">{passed}</div>
            <div class="metric-label">Passed</div>
          </div>
          <div class="metric-card">
            <div class="metric-value" style="color: #ff6b6b;">{failed}</div>
            <div class="metric-label">Failed</div>
          </div>
          <div class="metric-card">
            <div class="metric-value" style="color: #ffbe00;">4</div>
            <div class="metric-label">Active Rules</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.scan_history:
            st.markdown('<p class="section-header">Recent Scans</p>', unsafe_allow_html=True)
            for scan in reversed(st.session_state.scan_history[-5:]):
                badge_class = "badge-pass" if scan["status"] == "PASSED" else "badge-fail"
                st.markdown(f"""
                <div class="result-card" style="margin-bottom:8px;">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                      <p style="color:rgba(255,255,255,0.85); margin:0; font-size:0.82rem; font-weight:500;">{scan['filename'][:25]}{'...' if len(scan['filename'])>25 else ''}</p>
                      <p style="color:rgba(255,255,255,0.3); margin:0; font-size:0.72rem;">{scan['timestamp']}</p>
                    </div>
                    <span class="{badge_class}">{scan['status']}</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)


# ─── Page: Compliance Rules ────────────────────────────────────────────────────
elif page == "⚙️ Compliance Rules":
    st.markdown("""
    <div class="hero-header">
      <h1 class="hero-title">Compliance Rules Manager</h1>
      <p class="hero-subtitle">Customize the compliance checks applied to your documents</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<p class="section-header">Configure Rules</p>', unsafe_allow_html=True)

    rules = st.session_state.compliance_rules

    with st.expander("🔍 Rule 1 — PII / Personal Information Detection", expanded=True):
        col1, col2 = st.columns([1, 4])
        with col1:
            rules["pii_check"] = st.toggle("Enable", value=rules["pii_check"], key="pii_toggle")
        with col2:
            rules["pii_description"] = st.text_area(
                "Rule description / prompt instructions",
                value=rules["pii_description"],
                key="pii_desc",
                height=80
            )

    with st.expander("🔒 Rule 2 — Confidential Information Detection", expanded=True):
        col1, col2 = st.columns([1, 4])
        with col1:
            rules["confidential_check"] = st.toggle("Enable", value=rules["confidential_check"], key="conf_toggle")
        with col2:
            rules["confidential_description"] = st.text_area(
                "Rule description / prompt instructions",
                value=rules["confidential_description"],
                key="conf_desc",
                height=80
            )

    with st.expander("🔤 Rule 3 — Encoding Consistency Check", expanded=True):
        col1, col2 = st.columns([1, 4])
        with col1:
            rules["encoding_check"] = st.toggle("Enable", value=rules["encoding_check"], key="enc_toggle")
        with col2:
            rules["encoding_description"] = st.text_area(
                "Rule description / prompt instructions",
                value=rules["encoding_description"],
                key="enc_desc",
                height=80
            )

    with st.expander("🚫 Rule 4 — Abusive & Unlawful Content Detection", expanded=True):
        col1, col2 = st.columns([1, 4])
        with col1:
            rules["abusive_check"] = st.toggle("Enable", value=rules["abusive_check"], key="abu_toggle")
        with col2:
            rules["abusive_description"] = st.text_area(
                "Rule description / prompt instructions",
                value=rules["abusive_description"],
                key="abu_desc",
                height=80
            )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Save Rules", use_container_width=False):
        st.session_state.compliance_rules = rules
        st.success("✅ Compliance rules updated successfully!")


# ─── Page: Reports ─────────────────────────────────────────────────────────────
elif page == "📊 Reports":
    st.markdown("""
    <div class="hero-header">
      <h1 class="hero-title">Compliance Reports</h1>
      <p class="hero-subtitle">View detailed AI-generated compliance analysis reports</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.scan_history:
        st.markdown("""
        <div style="text-align:center; padding:4rem 2rem; color:rgba(255,255,255,0.3);">
          <p style="font-size:3rem;">📭</p>
          <p style="font-size:1.1rem; font-weight:500;">No reports yet</p>
          <p style="font-size:0.85rem;">Upload and scan a PDF to generate your first compliance report</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for i, scan in enumerate(reversed(st.session_state.scan_history)):
            status_badge = '<span class="badge-pass">PASSED</span>' if scan["status"] == "PASSED" else '<span class="badge-fail">FAILED</span>'
            with st.expander(f"📄 {scan['filename']} — {scan['timestamp']}", expanded=(i == 0)):
                st.markdown(f"""
                <div style="display:flex; gap:12px; align-items:center; margin-bottom:1rem;">
                  {status_badge}
                  <span style="color:rgba(255,255,255,0.4); font-size:0.8rem;">Scanned: {scan['timestamp']}</span>
                </div>
                """, unsafe_allow_html=True)

                if "report" in scan:
                    report = scan["report"]
                    for check_name, check_result in report.items():
                        if check_name == "_summary":
                            continue
                        is_pass = check_result.get("status") == "PASS"
                        card_class = "result-card-pass" if is_pass else "result-card-fail"
                        badge_class = "badge-pass" if is_pass else "badge-fail"
                        badge_text = "PASS" if is_pass else "FAIL"

                        flagged = check_result.get("flagged_pages", [])
                        pages_html = ""
                        if flagged:
                            pages_html = "<div style='margin-top:8px;'>" + "".join(
                                [f'<span style="background:rgba(255,107,107,0.15); color:#ff9090; border-radius:6px; padding:2px 8px; font-size:0.75rem; margin-right:6px; font-family: JetBrains Mono, monospace;">Page {p}</span>'
                                 for p in flagged]
                            ) + "</div>"

                        st.markdown(f"""
                        <div class="result-card {card_class}">
                          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="color:white; font-weight:600; font-size:0.9rem;">{check_name}</span>
                            <span class="{badge_class}">{badge_text}</span>
                          </div>
                          <p style="color:rgba(255,255,255,0.6); font-size:0.83rem; margin:0; line-height:1.5;">{check_result.get('details', 'No details available')}</p>
                          {pages_html}
                        </div>
                        """, unsafe_allow_html=True)

                report_json = json.dumps(scan, indent=2, default=str)
                st.download_button(
                    "⬇️ Download JSON Report",
                    data=report_json,
                    file_name=f"compliance_report_{scan['filename']}.json",
                    mime="application/json",
                    key=f"dl_{i}"
                )


# ─── Page: History ─────────────────────────────────────────────────────────────
elif page == "📜 History":
    st.markdown("""
    <div class="hero-header">
      <h1 class="hero-title">Scan History</h1>
      <p class="hero-subtitle">Track all your previous compliance scans</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.scan_history:
        st.info("No scans yet. Upload a PDF to get started!")
    else:
        cols = st.columns([3, 2, 2, 1])
        for col, header in zip(cols, ["Filename", "Timestamp", "Status", "Issues"]):
            col.markdown(f'<p style="color:rgba(255,255,255,0.4); font-size:0.75rem; font-weight:600; text-transform:uppercase; letter-spacing:1px;">{header}</p>', unsafe_allow_html=True)

        st.markdown('<hr style="margin: 0.5rem 0;">', unsafe_allow_html=True)

        for scan in reversed(st.session_state.scan_history):
            cols = st.columns([3, 2, 2, 1])
            badge_class = "badge-pass" if scan["status"] == "PASSED" else "badge-fail"
            with cols[0]:
                st.markdown(f'<p style="color:rgba(255,255,255,0.85); font-size:0.85rem; margin:0; padding:6px 0;">{scan["filename"][:30]}</p>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f'<p style="color:rgba(255,255,255,0.45); font-size:0.8rem; margin:0; padding:6px 0;">{scan["timestamp"]}</p>', unsafe_allow_html=True)
            with cols[2]:
                st.markdown(f'<span class="{badge_class}">{scan["status"]}</span>', unsafe_allow_html=True)
            with cols[3]:
                issues = scan.get("total_issues", 0)
                color = "#ff6b6b" if issues > 0 else "#00ff78"
                st.markdown(f'<p style="color:{color}; font-weight:600; font-size:0.9rem; margin:0; padding:6px 0;">{issues}</p>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Clear History"):
            st.session_state.scan_history = []
            st.rerun()