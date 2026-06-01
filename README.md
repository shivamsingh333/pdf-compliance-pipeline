# 🛡️ ComplianceAI — PDF Compliance Scanner

> An AI-powered pipeline that automatically scans PDF documents for compliance violations using LangGraph orchestration and Generative AI.

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red?style=flat-square&logo=streamlit)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green?style=flat-square)
![Groq](https://img.shields.io/badge/Groq-LLaMA3-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## 📌 What is this project?

ComplianceAI is a full-stack AI pipeline that allows users to upload any text-based PDF document and automatically check it for compliance violations — page by page — using the power of Large Language Models.

Instead of manually reading hundreds of pages, this tool scans the document in seconds and generates a detailed report highlighting exactly which pages contain issues and why.

---

## ✨ Features

- 📄 **PDF Upload UI** — Drag and drop any text-based PDF
- 🔍 **PII Detection** — Flags emails, phone numbers, SSNs, credit card numbers
- 🔒 **Confidential Info Detection** — Detects trade secrets, internal financials, sensitive IP
- 🔤 **UTF-8 Encoding Check** — Validates encoding consistency (English only)
- 🚫 **Abusive Content Detection** — Flags offensive, harmful, or unlawful content
- ⚙️ **Editable Compliance Rules** — Customize each rule's prompt via the UI
- 📊 **Detailed Reports** — Per-check results with flagged page numbers
- ⬇️ **Downloadable JSON Reports** — Export compliance reports
- 📜 **Scan History** — Track all previous scans in one place

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **UI / Frontend** | Streamlit |
| **Pipeline Orchestration** | LangGraph |
| **AI / LLM** | Groq (LLaMA 3 70B) |
| **PDF Processing** | PyMuPDF (fitz) + pdfplumber |
| **Language** | Python 3.11+ |
| **Encoding Detection** | chardet |
| **Deployment** | Streamlit Cloud |

---

## 🔁 How the Pipeline Works

```
PDF Upload
    │
    ▼
Extract text page-by-page (PyMuPDF)
    │
    ▼
LangGraph Pipeline starts
    │
    ├──► Node 1: PII Detection       (Regex + LLM)
    ├──► Node 2: Confidential Info   (LLM)
    ├──► Node 3: Encoding Check      (Regex)
    └──► Node 4: Abusive Content     (Keyword filter + LLM)
    │
    ▼
Aggregate Results
    │
    ▼
Compliance Report (Pass / Fail per check + flagged pages)
```

Each node in the LangGraph pipeline reads from a shared `ComplianceState` and writes its result back — making it easy to add new compliance rules without changing the rest of the code.

---

## 📁 Project Structure

```
pdf_compliance_pipeline/
├── app.py                        ← Main Streamlit UI (4 pages)
├── requirements.txt              ← All dependencies
├── .gitignore
├── utils/
│   ├── __init__.py
│   └── pdf_extractor.py          ← PDF → page-by-page text extraction
└── langgraph_pipeline/
    ├── __init__.py
    └── pipeline.py               ← LangGraph nodes + pipeline builder
```

---

## 🚀 Run Locally

**1. Clone the repository**
```bash
git clone https://github.com/shivamsingh333/pdf-compliance-pipeline.git
cd pdf-compliance-pipeline
```

**2. Install dependencies**
```bash
pip3 install -r requirements.txt
```

**3. Run the app**
```bash
python3 -m streamlit run app.py
```

**4. Open your browser at** `http://localhost:8501`

**5. Enter your Groq API key** in the sidebar → Upload a PDF → Click **Run Compliance Scan**

---

## 🔑 API Keys

This project supports multiple AI providers. Get a free key from any of these:

| Provider | Free Tier | Link |
|----------|-----------|------|
| **Groq** ✅ Recommended | Yes (fast) | [console.groq.com](https://console.groq.com) |
| Anthropic Claude | Paid | [console.anthropic.com](https://console.anthropic.com) |
| Google Gemini | Yes | [aistudio.google.com](https://aistudio.google.com) |
| OpenAI | Paid | [platform.openai.com](https://platform.openai.com) |

> API keys are entered in the app sidebar — never stored in code.

---

## 📸 Screenshots

> The app has a dark-themed UI with 4 pages:
> - **Scan PDF** — Upload and run compliance checks
> - **Compliance Rules** — Edit and toggle each rule
> - **Reports** — View detailed per-check results
> - **History** — Track all previous scans

---

## 🧩 Compliance Checks

| # | Check | Method | What it detects |
|---|-------|--------|-----------------|
| 1 | PII Detection | Regex + LLM | Emails, phones, SSNs, credit cards |
| 2 | Confidential Info | LLM | Trade secrets, internal docs, IP |
| 3 | UTF-8 Encoding | Regex | Non-English text, corrupt characters |
| 4 | Abusive Content | Keyword + LLM | Offensive or unlawful language |

---

## 🌐 Live Demo

👉 [Click here to try the live app](https://shivamsingh333-pdf-compliance-pipeline-app.streamlit.app)

---

## 👨‍💻 Author

Built as part of an AI Pipeline project using Streamlit, LangGraph, Groq, and PyMuPDF.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).