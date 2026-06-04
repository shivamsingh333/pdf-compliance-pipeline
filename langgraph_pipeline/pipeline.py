"""
LangGraph Compliance Pipeline — Enterprise Matrix Edition
Uses structured Enterprise Auditor prompt for each compliance check.
Returns severity, violation text, page number, explanation, remediation.
"""
from typing import TypedDict, Annotated
import json
import re
import operator


# ─── State ────────────────────────────────────────────────────────────────────
class ComplianceState(TypedDict):
    pages: list
    filename: str
    rules_config: dict
    api_key: str
    provider: str
    model: str
    retrieved_rules: str
    report: dict
    errors: Annotated[list, operator.add]


# ─── AI Client Factory ────────────────────────────────────────────────────────
def get_ai_client(provider: str, api_key: str, model: str):
    if "Groq" in provider:
        from groq import Groq
        client = Groq(api_key=api_key)
        def call(system: str, user: str) -> str:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user",   "content": user}],
                temperature=0.1, max_tokens=3000
            )
            return r.choices[0].message.content
        return call

    elif "Anthropic" in provider:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        def call(system: str, user: str) -> str:
            m = client.messages.create(model=model, max_tokens=3000,
                system=system, messages=[{"role": "user", "content": user}])
            return m.content[0].text
        return call

    elif "Google" in provider:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gm = genai.GenerativeModel(model)
        def call(system: str, user: str) -> str:
            return gm.generate_content(f"{system}\n\n{user}").text
        return call

    elif "OpenAI" in provider:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        def call(system: str, user: str) -> str:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user",   "content": user}],
                temperature=0.1, max_tokens=3000
            )
            return r.choices[0].message.content
        return call

    raise ValueError(f"Unknown provider: {provider}")


# ─── Enterprise Auditor System Prompt ────────────────────────────────────────
ENTERPRISE_SYSTEM_PROMPT = """You are an Enterprise Compliance Auditor. Analyze the document and respond with ONLY a JSON object.

CRITICAL RULES:
- Your ENTIRE response must be a single JSON object
- Do NOT write any text before or after the JSON
- Do NOT use markdown code blocks or backticks
- Do NOT write "Here is..." or any explanation
- Start your response with {{ and end with }}

For each compliance control:
1. Determine PASS or FAIL
2. Find the exact violation text (max 80 chars), empty string if none
3. Find the page number of the violation
4. Assign severity: Critical, High, Medium, Low, or None
5. Write a short explanation (1 sentence)
6. Suggest a specific remediation

Severity Guide:
- Critical: passwords, API keys, Aadhaar numbers exposed
- High: emails, phone numbers, PAN cards found
- Medium: internal references, partial identifiers
- Low: encoding issues, informal language
- None: no violation found (PASS)

YOUR RESPONSE MUST BE EXACTLY THIS JSON STRUCTURE:
{{
  "status": "PASS",
  "severity": "None",
  "flagged_pages": [],
  "violation_text": "",
  "explanation": "No violations found.",
  "remediation": "No action required.",
  "evidence": []
}}

OR if violations found:
{{
  "status": "FAIL",
  "severity": "High",
  "flagged_pages": [1, 2],
  "violation_text": "john.doe@company.com",
  "explanation": "Email address found on page 1.",
  "remediation": "Redact all email addresses before sharing.",
  "evidence": ["email on page 1: john.doe@company.com"]
}}

{retrieved_rules}"""


def build_system_prompt(retrieved_rules: str) -> str:
    return ENTERPRISE_SYSTEM_PROMPT.format(retrieved_rules=retrieved_rules)


def build_check_prompt(control_name: str, control_description: str, pages_text: str) -> str:
    return f"""COMPLIANCE CONTROL: {control_name}
CONTROL DESCRIPTION: {control_description}

Analyze the following document content page by page.

DOCUMENT CONTENT:
{pages_text[:8000]}

Return ONLY the JSON object as specified. No markdown, no extra text."""


def safe_parse(response: str) -> dict:
    """
    Robustly parse AI JSON response.
    Handles markdown fences, leading text, and extracts
    the first complete JSON object found in the response.
    """
    import json as _json
    clean = response.strip()
    # Remove markdown fences
    clean = re.sub(r"```json\s*", "", clean)
    clean = re.sub(r"```\s*",     "", clean)
    clean = clean.strip()

    # Try direct parse first
    try:
        return _json.loads(clean)
    except _json.JSONDecodeError:
        pass

    # Extract first complete JSON object via brace matching
    start = clean.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(clean[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return _json.loads(clean[start:i+1])
                    except _json.JSONDecodeError:
                        break

    raise ValueError(f"Could not parse JSON from response: {clean[:200]}")


# ─── Node 1: Inject Credentials ──────────────────────────────────────────────
def inject_credentials(state: ComplianceState) -> dict:
    return {"report": {}, "retrieved_rules": "", "errors": []}


# ─── Node 2: RAG — Retrieve Rules ────────────────────────────────────────────
def retrieve_rules(state: ComplianceState) -> dict:
    try:
        from utils.vector_store import retrieve_relevant_rules
        pages = state["pages"]
        query = " ".join([p["text"][:300] for p in pages[:2] if p.get("has_text")])
        if not query.strip():
            query = "document compliance check PII confidential information"
        rules_text = retrieve_relevant_rules(query, top_k=6)
        return {"retrieved_rules": rules_text}
    except Exception as e:
        from utils.vector_store import _get_default_rules_text
        return {"retrieved_rules": _get_default_rules_text(),
                "errors": [f"Vector DB fallback: {str(e)}"]}


# ─── Node 3: PII Control ─────────────────────────────────────────────────────
def check_pii(state: ComplianceState) -> dict:
    rules_config = state.get("rules_config", {})
    if not rules_config.get("pii_check", True):
        report = dict(state.get("report", {}))
        report["PII & Personal Data"] = {
            "status": "SKIP", "severity": "None",
            "flagged_pages": [], "violation_text": "",
            "explanation": "Control disabled by admin.",
            "remediation": "Enable this control to check for PII.",
            "evidence": []
        }
        return {"report": report}

    pages = state["pages"]

    # Fast regex pre-scan
    pii_patterns = {
        "Email":        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "Phone":        r'(\+?91[-.\s]?)?[6-9]\d{9}|(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}',
        "Aadhaar":      r'\b\d{4}\s?\d{4}\s?\d{4}\b',
        "PAN":          r'\b[A-Z]{5}[0-9]{4}[A-Z]\b',
        "SSN":          r'\b\d{3}-\d{2}-\d{4}\b',
        "Credit Card":  r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        "API Key":      r'\b(sk-[a-zA-Z0-9]{20,}|gsk_[a-zA-Z0-9]{20,}|AIza[a-zA-Z0-9]{35})\b',
        "Password":     r'(?i)(password|passwd|pwd)\s*[:=]\s*\S+',
    }

    flagged_pages = []
    evidence      = []
    violation_text = ""

    for page in pages:
        text = page["text"]
        for pii_type, pattern in pii_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                flagged_pages.append(page["page_num"])
                snippet = match.group(0)[:80]
                evidence.append(f"{pii_type} on page {page['page_num']}: \"{snippet}\"")
                if not violation_text:
                    violation_text = snippet
                break

    if flagged_pages:
        severity = "Critical" if any(k in str(evidence) for k in ["API Key", "Password", "Aadhaar"]) else "High"
        result = {
            "status":         "FAIL",
            "severity":       severity,
            "flagged_pages":  list(set(flagged_pages)),
            "violation_text": violation_text,
            "explanation":    f"PII detected on {len(set(flagged_pages))} page(s): {', '.join(evidence[:2])}",
            "remediation":    "Redact or anonymize all personal identifiers before document distribution.",
            "evidence":       evidence[:5]
        }
    else:
        try:
            ai = get_ai_client(state["provider"], state["api_key"], state["model"])
            pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:500]}" for p in pages])
            system   = build_system_prompt(state.get("retrieved_rules", ""))
            response = ai(system, build_check_prompt(
                "PII & Personal Data",
                rules_config.get("pii_description", "Flag emails, phones, Aadhaar, PAN, SSN, credit cards, API keys"),
                pages_text
            ))
            result = safe_parse(response)
        except Exception as e:
            result = {
                "status": "PASS", "severity": "None",
                "flagged_pages": [], "violation_text": "",
                "explanation": f"Regex scan clear. AI note: {str(e)[:80]}",
                "remediation": "No action required.", "evidence": []
            }

    report = dict(state.get("report", {}))
    report["PII & Personal Data"] = result
    return {"report": report}


# ─── Node 4: Confidential Info Control ───────────────────────────────────────
def check_confidential(state: ComplianceState) -> dict:
    rules_config = state.get("rules_config", {})
    if not rules_config.get("confidential_check", True):
        report = dict(state.get("report", {}))
        report["Confidential Information"] = {
            "status": "SKIP", "severity": "None",
            "flagged_pages": [], "violation_text": "",
            "explanation": "Control disabled.", "remediation": "", "evidence": []
        }
        return {"report": report}

    try:
        ai = get_ai_client(state["provider"], state["api_key"], state["model"])
        pages = state["pages"]
        pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:600]}" for p in pages])
        system   = build_system_prompt(state.get("retrieved_rules", ""))
        response = ai(system, build_check_prompt(
            "Confidential Information",
            rules_config.get("confidential_description", "Flag trade secrets, internal financials, API keys, passwords, IP"),
            pages_text
        ))
        result = safe_parse(response)
    except Exception as e:
        result = {
            "status": "ERROR", "severity": "Medium",
            "flagged_pages": [], "violation_text": "",
            "explanation": str(e)[:150],
            "remediation": "Retry with a valid API key.", "evidence": []
        }

    report = dict(state.get("report", {}))
    report["Confidential Information"] = result
    return {"report": report}


# ─── Node 5: Encoding Control ─────────────────────────────────────────────────
def check_encoding(state: ComplianceState) -> dict:
    rules_config = state.get("rules_config", {})
    if not rules_config.get("encoding_check", True):
        report = dict(state.get("report", {}))
        report["Encoding & Language"] = {
            "status": "SKIP", "severity": "None",
            "flagged_pages": [], "violation_text": "",
            "explanation": "Control disabled.", "remediation": "", "evidence": []
        }
        return {"report": report}

    flagged_pages  = []
    evidence       = []
    violation_text = ""

    for page in state["pages"]:
        issues = page.get("encoding_issues", [])
        if issues:
            flagged_pages.append(page["page_num"])
            for issue in issues:
                evidence.append(f"Page {page['page_num']}: {issue}")
            if not violation_text:
                violation_text = issues[0][:80]

    if flagged_pages:
        result = {
            "status":         "FAIL",
            "severity":       "Low",
            "flagged_pages":  flagged_pages,
            "violation_text": violation_text,
            "explanation":    f"Encoding issues found on {len(flagged_pages)} page(s).",
            "remediation":    "Re-export the document as UTF-8 encoded PDF with English text only.",
            "evidence":       evidence[:5]
        }
    else:
        result = {
            "status":         "PASS",
            "severity":       "None",
            "flagged_pages":  [],
            "violation_text": "",
            "explanation":    "All pages use consistent UTF-8 encoding with English text.",
            "remediation":    "No action required.",
            "evidence":       []
        }

    report = dict(state.get("report", {}))
    report["Encoding & Language"] = result
    return {"report": report}


# ─── Node 6: Abusive Content Control ─────────────────────────────────────────
def check_abusive_content(state: ComplianceState) -> dict:
    rules_config = state.get("rules_config", {})
    if not rules_config.get("abusive_check", True):
        report = dict(state.get("report", {}))
        report["Abusive & Unlawful Content"] = {
            "status": "SKIP", "severity": "None",
            "flagged_pages": [], "violation_text": "",
            "explanation": "Control disabled.", "remediation": "", "evidence": []
        }
        return {"report": report}

    keywords = ["kill", "murder", "threat", "illegal", "fraud", "scam",
                "drug", "weapon", "bomb", "hate", "racist", "slur", "abuse"]
    pages        = state["pages"]
    pre_flagged  = [p["page_num"] for p in pages
                    if any(kw in p["text"].lower() for kw in keywords)]

    try:
        ai = get_ai_client(state["provider"], state["api_key"], state["model"])
        pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:500]}" for p in pages])
        system   = build_system_prompt(state.get("retrieved_rules", ""))
        response = ai(system, build_check_prompt(
            "Abusive & Unlawful Content",
            rules_config.get("abusive_description", "Flag abusive, offensive, or unlawful content"),
            pages_text
        ))
        result = safe_parse(response)
        if pre_flagged and result.get("status") == "PASS":
            result["explanation"] += f" Keywords flagged pages {pre_flagged} for manual review."
    except Exception as e:
        result = {
            "status":         "PASS" if not pre_flagged else "WARN",
            "severity":       "None" if not pre_flagged else "Medium",
            "flagged_pages":  pre_flagged,
            "violation_text": "",
            "explanation":    f"AI check note: {str(e)[:80]}. Keyword scan: {'issues on pages ' + str(pre_flagged) if pre_flagged else 'clear'}",
            "remediation":    "Manual review recommended for flagged pages." if pre_flagged else "No action required.",
            "evidence":       []
        }

    report = dict(state.get("report", {}))
    report["Abusive & Unlawful Content"] = result
    return {"report": report}


# ─── Node 7: Aggregate ────────────────────────────────────────────────────────
def aggregate_results(state: ComplianceState) -> dict:
    report  = state.get("report", {})
    failed  = [k for k, v in report.items() if v.get("status") == "FAIL"]
    passed  = [k for k, v in report.items() if v.get("status") == "PASS"]
    skipped = [k for k, v in report.items() if v.get("status") == "SKIP"]

    severity_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "None": 0}
    highest_sev = max(
        (severity_order.get(v.get("severity", "None"), 0) for v in report.values()),
        default=0
    )
    sev_map_rev = {4: "Critical", 3: "High", 2: "Medium", 1: "Low", 0: "None"}

    report["_summary"] = {
        "total_controls":    len(report),
        "failed_controls":   len(failed),
        "passed_controls":   len(passed),
        "skipped_controls":  len(skipped),
        "highest_severity":  sev_map_rev[highest_sev],
        "overall_status":    "FAIL" if failed else "PASS",
        "failed_controls_list": failed,
        "rules_source":      "Vector DB (RAG)" if state.get("retrieved_rules") else "Default"
    }
    return {"report": report}


# ─── Pipeline Builder ─────────────────────────────────────────────────────────
def build_pipeline(api_key: str, provider: str, model: str, rules_config: dict):
    from langgraph.graph import StateGraph, START, END

    def inject(state):
        return {
            "api_key":       api_key,
            "provider":      provider,
            "model":         model,
            "rules_config":  rules_config,
            "report":        {},
            "retrieved_rules": "",
            "errors":        []
        }

    b = StateGraph(ComplianceState)
    b.add_node("inject_credentials",    inject)
    b.add_node("retrieve_rules",        retrieve_rules)
    b.add_node("check_pii",             check_pii)
    b.add_node("check_confidential",    check_confidential)
    b.add_node("check_encoding",        check_encoding)
    b.add_node("check_abusive_content", check_abusive_content)
    b.add_node("aggregate_results",     aggregate_results)

    b.add_edge(START,                   "inject_credentials")
    b.add_edge("inject_credentials",    "retrieve_rules")
    b.add_edge("retrieve_rules",        "check_pii")
    b.add_edge("check_pii",             "check_confidential")
    b.add_edge("check_confidential",    "check_encoding")
    b.add_edge("check_encoding",        "check_abusive_content")
    b.add_edge("check_abusive_content", "aggregate_results")
    b.add_edge("aggregate_results",     END)

    return b.compile()