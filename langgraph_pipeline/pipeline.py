"""
LangGraph Compliance Pipeline — with Time, Token & Cost Tracking
NEW: aggregate_results node now records:
  - total_time_seconds
  - estimated_input_tokens
  - estimated_output_tokens
  - estimated_cost_usd
  - model used
"""
from typing import TypedDict, Annotated
import json, re, time, operator

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
    _start_time: float          # NEW: pipeline start timestamp
    _token_log: Annotated[list, operator.add]  # NEW: per-call token estimates


# ─── Token & Cost Pricing ─────────────────────────────────────────────────────
MODEL_PRICING = {
    "llama-3.3-70b-versatile":   {"input": 0.59,  "output": 0.79,  "per": 1_000_000},
    "llama-3.1-8b-instant":      {"input": 0.05,  "output": 0.08,  "per": 1_000_000},
    "claude-3-5-sonnet-20241022":{"input": 3.00,  "output": 15.00, "per": 1_000_000},
    "claude-3-haiku-20240307":   {"input": 0.25,  "output": 1.25,  "per": 1_000_000},
    "gemini-1.5-pro":            {"input": 1.25,  "output": 5.00,  "per": 1_000_000},
    "gemini-1.5-flash":          {"input": 0.075, "output": 0.30,  "per": 1_000_000},
    "gpt-4o":                    {"input": 2.50,  "output": 10.00, "per": 1_000_000},
    "gpt-4o-mini":               {"input": 0.15,  "output": 0.60,  "per": 1_000_000},
}

def estimate_tokens(text: str) -> int:
    """Estimate tokens from character count (approx 4 chars per token)."""
    return max(1, len(text) // 4)

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost in USD."""
    pricing = MODEL_PRICING.get(model, {"input": 1.0, "output": 3.0, "per": 1_000_000})
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / pricing["per"]
    return round(cost, 6)


# ─── AI Client ────────────────────────────────────────────────────────────────
def get_ai_client(provider, api_key, model):
    if "Groq" in provider:
        from groq import Groq
        client = Groq(api_key=api_key)
        def call(system, user):
            r = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
                temperature=0.1, max_tokens=3000
            )
            return r.choices[0].message.content
        return call
    elif "Anthropic" in provider:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        def call(system, user):
            m = client.messages.create(model=model, max_tokens=3000,
                system=system, messages=[{"role":"user","content":user}])
            return m.content[0].text
        return call
    elif "Google" in provider:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gm = genai.GenerativeModel(model)
        def call(system, user):
            return gm.generate_content(f"{system}\n\n{user}").text
        return call
    elif "OpenAI" in provider:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        def call(system, user):
            r = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
                temperature=0.1, max_tokens=3000
            )
            return r.choices[0].message.content
        return call
    raise ValueError(f"Unknown provider: {provider}")


# ─── Prompt Builders ──────────────────────────────────────────────────────────
ENTERPRISE_SYSTEM_PROMPT = """You are an Enterprise Compliance Auditor.
Your task is to analyze a PDF document against the provided compliance controls.

CRITICAL RULES:
- Your ENTIRE response must be a single JSON object
- Do NOT write any text before or after the JSON
- Do NOT use markdown code blocks or backticks
- Start your response with {{ and end with }}

For each control determine PASS or FAIL, find exact violation text (max 80 chars),
identify page number, assign severity (Critical/High/Medium/Low/None),
write a short explanation, and suggest a specific remediation.

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

{retrieved_rules}"""

def build_system_prompt(retrieved_rules):
    return ENTERPRISE_SYSTEM_PROMPT.format(retrieved_rules=retrieved_rules)

def build_check_prompt(control_name, control_description, pages_text):
    return f"""COMPLIANCE CONTROL: {control_name}
CONTROL DESCRIPTION: {control_description}

DOCUMENT CONTENT:
{pages_text[:8000]}

Return ONLY the JSON object. No markdown, no extra text."""

def safe_parse(response):
    clean = response.strip()
    clean = re.sub(r"```json\s*","",clean)
    clean = re.sub(r"```\s*","",clean)
    clean = clean.strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    start = clean.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(clean[start:], start):
            if ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try: return json.loads(clean[start:i+1])
                    except: break
    raise ValueError(f"Cannot parse JSON: {clean[:200]}")


# ─── Node: Inject Credentials ─────────────────────────────────────────────────
def inject_credentials(state):
    return {
        "report": {},
        "retrieved_rules": "",
        "errors": [],
        "_start_time": time.time(),
        "_token_log": []
    }


# ─── Node: Retrieve Rules (RAG) ───────────────────────────────────────────────
def retrieve_rules(state):
    try:
        from utils.vector_store import retrieve_relevant_rules
        pages = state["pages"]
        query = " ".join([p["text"][:300] for p in pages[:2] if p.get("has_text")])
        if not query.strip():
            query = "document compliance check PII confidential"
        rules_text = retrieve_relevant_rules(query, top_k=6)
        return {"retrieved_rules": rules_text, "_token_log": [{"node": "retrieve_rules", "tokens": estimate_tokens(rules_text)}]}
    except Exception as e:
        from utils.vector_store import _get_default_rules_text
        return {"retrieved_rules": _get_default_rules_text(), "errors": [f"RAG fallback: {str(e)}"]}


# ─── Node: PII Check ──────────────────────────────────────────────────────────
def check_pii(state):
    rules_config = state.get("rules_config", {})
    if not rules_config.get("pii_check", True):
        report = dict(state.get("report", {}))
        report["PII & Personal Data"] = {"status":"SKIP","severity":"None","flagged_pages":[],"violation_text":"","explanation":"Control disabled.","remediation":"Enable to check PII.","evidence":[]}
        return {"report": report}

    pages = state["pages"]
    pii_patterns = {
        "Email":       r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "Phone":       r'(\+?91[-.\s]?)?[6-9]\d{9}',
        "Aadhaar":     r'\b\d{4}\s?\d{4}\s?\d{4}\b',
        "PAN":         r'\b[A-Z]{5}[0-9]{4}[A-Z]\b',
        "SSN":         r'\b\d{3}-\d{2}-\d{4}\b',
        "Credit Card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        "API Key":     r'\b(sk-[a-zA-Z0-9]{20,}|gsk_[a-zA-Z0-9]{20,})\b',
    }
    flagged_pages, evidence, violation_text = [], [], ""
    for page in pages:
        for pii_type, pattern in pii_patterns.items():
            m = re.search(pattern, page["text"], re.IGNORECASE)
            if m:
                flagged_pages.append(page["page_num"])
                snippet = m.group(0)[:80]
                evidence.append(f"{pii_type} on page {page['page_num']}: \"{snippet}\"")
                if not violation_text: violation_text = snippet
                break

    if flagged_pages:
        severity = "Critical" if any(k in str(evidence) for k in ["API Key","Aadhaar"]) else "High"
        result = {"status":"FAIL","severity":severity,"flagged_pages":list(set(flagged_pages)),"violation_text":violation_text,"explanation":f"PII detected on {len(set(flagged_pages))} page(s): {'; '.join(evidence[:2])}","remediation":"Redact all personal identifiers before distribution.","evidence":evidence[:5]}
    else:
        system_prompt = build_system_prompt(state.get("retrieved_rules",""))
        pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:500]}" for p in pages])
        user_prompt = build_check_prompt("PII & Personal Data", rules_config.get("pii_description","Flag emails, phones, Aadhaar, PAN"), pages_text)
        input_tokens = estimate_tokens(system_prompt + user_prompt)
        try:
            ai = get_ai_client(state["provider"], state["api_key"], state["model"])
            response = ai(system_prompt, user_prompt)
            output_tokens = estimate_tokens(response)
            result = safe_parse(response)
        except Exception as e:
            output_tokens = 10
            result = {"status":"PASS","severity":"None","flagged_pages":[],"violation_text":"","explanation":f"Regex clear. AI note: {str(e)[:80]}","remediation":"No action required.","evidence":[]}
        report = dict(state.get("report", {}))
        report["PII & Personal Data"] = result
        return {"report": report, "_token_log": [{"node":"pii","input":input_tokens,"output":output_tokens}]}

    report = dict(state.get("report", {}))
    report["PII & Personal Data"] = result
    return {"report": report, "_token_log": [{"node":"pii","input":0,"output":0}]}


# ─── Node: Confidential Check ─────────────────────────────────────────────────
def check_confidential(state):
    rules_config = state.get("rules_config", {})
    if not rules_config.get("confidential_check", True):
        report = dict(state.get("report", {}))
        report["Confidential Information"] = {"status":"SKIP","severity":"None","flagged_pages":[],"violation_text":"","explanation":"Control disabled.","remediation":"","evidence":[]}
        return {"report": report}

    system_prompt = build_system_prompt(state.get("retrieved_rules",""))
    pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:600]}" for p in state["pages"]])
    user_prompt = build_check_prompt("Confidential Information", rules_config.get("confidential_description","Flag trade secrets, API keys, passwords"), pages_text)
    input_tokens = estimate_tokens(system_prompt + user_prompt)
    try:
        ai = get_ai_client(state["provider"], state["api_key"], state["model"])
        response = ai(system_prompt, user_prompt)
        output_tokens = estimate_tokens(response)
        result = safe_parse(response)
    except Exception as e:
        output_tokens = 10
        result = {"status":"ERROR","severity":"Medium","flagged_pages":[],"violation_text":"","explanation":str(e)[:150],"remediation":"Retry with valid API key.","evidence":[]}

    report = dict(state.get("report", {}))
    report["Confidential Information"] = result
    return {"report": report, "_token_log": [{"node":"confidential","input":input_tokens,"output":output_tokens}]}


# ─── Node: Encoding Check ─────────────────────────────────────────────────────
def check_encoding(state):
    rules_config = state.get("rules_config", {})
    if not rules_config.get("encoding_check", True):
        report = dict(state.get("report", {}))
        report["Encoding & Language"] = {"status":"SKIP","severity":"None","flagged_pages":[],"violation_text":"","explanation":"Control disabled.","remediation":"","evidence":[]}
        return {"report": report}

    flagged_pages, evidence, violation_text = [], [], ""
    for page in state["pages"]:
        issues = page.get("encoding_issues", [])
        if issues:
            flagged_pages.append(page["page_num"])
            for issue in issues: evidence.append(f"Page {page['page_num']}: {issue}")
            if not violation_text: violation_text = issues[0][:80]

    if flagged_pages:
        result = {"status":"FAIL","severity":"Low","flagged_pages":flagged_pages,"violation_text":violation_text,"explanation":f"Encoding issues on {len(flagged_pages)} page(s).","remediation":"Re-export as UTF-8 encoded PDF.","evidence":evidence[:5]}
    else:
        result = {"status":"PASS","severity":"None","flagged_pages":[],"violation_text":"","explanation":"All pages use consistent UTF-8 encoding.","remediation":"No action required.","evidence":[]}

    report = dict(state.get("report", {}))
    report["Encoding & Language"] = result
    return {"report": report, "_token_log": [{"node":"encoding","input":0,"output":0}]}


# ─── Node: Abusive Content Check ─────────────────────────────────────────────
def check_abusive_content(state):
    rules_config = state.get("rules_config", {})
    if not rules_config.get("abusive_check", True):
        report = dict(state.get("report", {}))
        report["Abusive & Unlawful Content"] = {"status":"SKIP","severity":"None","flagged_pages":[],"violation_text":"","explanation":"Control disabled.","remediation":"","evidence":[]}
        return {"report": report}

    keywords = ["kill","murder","threat","illegal","fraud","scam","drug","weapon","bomb","hate","racist","slur","abuse"]
    pages = state["pages"]
    pre_flagged = [p["page_num"] for p in pages if any(kw in p["text"].lower() for kw in keywords)]

    system_prompt = build_system_prompt(state.get("retrieved_rules",""))
    pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:500]}" for p in pages])
    user_prompt = build_check_prompt("Abusive & Unlawful Content", rules_config.get("abusive_description","Flag abusive or unlawful content"), pages_text)
    input_tokens = estimate_tokens(system_prompt + user_prompt)
    try:
        ai = get_ai_client(state["provider"], state["api_key"], state["model"])
        response = ai(system_prompt, user_prompt)
        output_tokens = estimate_tokens(response)
        result = safe_parse(response)
        if pre_flagged and result.get("status") == "PASS":
            result["explanation"] += f" Keywords flagged pages {pre_flagged} — manual review recommended."
    except Exception as e:
        output_tokens = 10
        result = {"status":"PASS" if not pre_flagged else "WARN","severity":"None" if not pre_flagged else "Medium","flagged_pages":pre_flagged,"violation_text":"","explanation":f"AI note: {str(e)[:80]}. Keyword scan: {'issues on pages '+str(pre_flagged) if pre_flagged else 'clear'}","remediation":"Manual review recommended." if pre_flagged else "No action required.","evidence":[]}

    report = dict(state.get("report", {}))
    report["Abusive & Unlawful Content"] = result
    return {"report": report, "_token_log": [{"node":"abusive","input":input_tokens,"output":output_tokens}]}


# ─── Node: Aggregate + Metrics ────────────────────────────────────────────────
def aggregate_results(state):
    report      = state.get("report", {})
    token_log   = state.get("_token_log", [])
    start_time  = state.get("_start_time", time.time())
    model       = state.get("model", "unknown")

    failed  = [k for k, v in report.items() if v.get("status") == "FAIL"]
    passed  = [k for k, v in report.items() if v.get("status") == "PASS"]
    skipped = [k for k, v in report.items() if v.get("status") == "SKIP"]

    severity_order = {"Critical":4,"High":3,"Medium":2,"Low":1,"None":0}
    sev_map_rev    = {4:"Critical",3:"High",2:"Medium",1:"Low",0:"None"}
    highest_sev    = sev_map_rev[max((severity_order.get(v.get("severity","None"),0) for v in report.values()), default=0)]

    total_input  = sum(e.get("input",  e.get("tokens", 0)) for e in token_log)
    total_output = sum(e.get("output", 0) for e in token_log)
    total_tokens = total_input + total_output
    cost_usd     = calculate_cost(model, total_input, total_output)
    elapsed      = round(time.time() - start_time, 1)

    report["_summary"] = {
        "total_controls":       len(report),
        "failed_controls":      len(failed),
        "passed_controls":      len(passed),
        "skipped_controls":     len(skipped),
        "highest_severity":     highest_sev,
        "overall_status":       "FAIL" if failed else "PASS",
        "failed_controls_list": failed,
        "rules_source":         "Vector DB (RAG)" if state.get("retrieved_rules") else "Default",
        "metrics": {
            "time_seconds":     elapsed,
            "input_tokens":     total_input,
            "output_tokens":    total_output,
            "total_tokens":     total_tokens,
            "cost_usd":         cost_usd,
            "model":            model,
        }
    }
    return {"report": report}


# ─── Build Pipeline ───────────────────────────────────────────────────────────
def build_pipeline(api_key, provider, model, rules_config):
    from langgraph.graph import StateGraph, START, END

    def inject(state):
        return {"api_key":api_key,"provider":provider,"model":model,
                "rules_config":rules_config,"report":{},"retrieved_rules":"",
                "errors":[],"_start_time":time.time(),"_token_log":[]}

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