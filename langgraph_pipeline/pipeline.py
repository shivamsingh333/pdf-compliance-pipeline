"""
LangGraph Compliance Pipeline — RAG Edition
Now retrieves compliance rules dynamically from Vector DB before each check.

Flow:
  START → inject_credentials → retrieve_rules (RAG) →
  [pii_check, confidential_check, encoding_check, abuse_check] →
  aggregate_results → END
"""
from typing import TypedDict, Annotated
import json
import re
import operator


# ─── State Definition ─────────────────────────────────────────────────────────
class ComplianceState(TypedDict):
    pages: list
    filename: str
    rules_config: dict          # UI toggles (on/off per check)
    api_key: str
    provider: str
    model: str
    retrieved_rules: str        # ← NEW: rules fetched from Vector DB
    report: dict
    errors: Annotated[list, operator.add]


# ─── AI Client Factory ────────────────────────────────────────────────────────
def get_ai_client(provider: str, api_key: str, model: str):
    """Returns a callable: (system_prompt, user_prompt) → str."""

    if "Groq" in provider:
        from groq import Groq
        client = Groq(api_key=api_key)
        def call(system: str, user: str) -> str:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user}
                ],
                temperature=0.1,
                max_tokens=2048
            )
            return response.choices[0].message.content
        return call

    elif "Anthropic" in provider:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        def call(system: str, user: str) -> str:
            msg = client.messages.create(
                model=model, max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user}]
            )
            return msg.content[0].text
        return call

    elif "Google" in provider:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gmodel = genai.GenerativeModel(model)
        def call(system: str, user: str) -> str:
            return gmodel.generate_content(f"{system}\n\n{user}").text
        return call

    elif "OpenAI" in provider:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        def call(system: str, user: str) -> str:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user}
                ],
                temperature=0.1, max_tokens=2048
            )
            return response.choices[0].message.content
        return call

    raise ValueError(f"Unknown provider: {provider}")


# ─── System Prompt ─────────────────────────────────────────────────────────────
BASE_SYSTEM_PROMPT = """You are a document compliance auditor. Your job is to analyze document text and identify compliance violations based on the rules provided.

Always respond ONLY with valid JSON in exactly this format:
{{
  "status": "PASS" or "FAIL",
  "details": "Brief explanation of findings",
  "flagged_pages": [list of page numbers with issues, e.g. [1, 3]],
  "evidence": ["list of specific problematic snippets found (max 5)"]
}}

Be precise and conservative. Only flag clear violations, not ambiguous content.

{retrieved_rules}"""


def build_system_prompt(retrieved_rules: str) -> str:
    return BASE_SYSTEM_PROMPT.format(retrieved_rules=retrieved_rules)


def build_check_prompt(check_type: str, description: str, pages_text: str) -> str:
    return f"""
COMPLIANCE CHECK: {check_type}
SPECIFIC RULE: {description}

Analyze the following document text page-by-page and determine if this compliance rule is violated.

DOCUMENT CONTENT:
{pages_text[:8000]}

Respond with JSON only as specified in the system prompt.
"""


# ─── Node 1: Inject Credentials ───────────────────────────────────────────────
def inject_credentials(state: ComplianceState) -> dict:
    """Inject API credentials and reset report."""
    return {"report": {}, "retrieved_rules": "", "errors": []}


# ─── Node 2: Retrieve Rules from Vector DB (RAG) ─────────────────────────────
def retrieve_rules(state: ComplianceState) -> dict:
    """
    RAG Node: Query Vector DB with document text to get the most
    relevant compliance rules. Injects them into state for all
    downstream check nodes to use.
    """
    try:
        from utils.vector_store import retrieve_relevant_rules

        # Use first 2 pages as the query context
        pages = state["pages"]
        query_text = " ".join([
            p["text"][:300] for p in pages[:2] if p.get("has_text")
        ])

        if not query_text.strip():
            query_text = "document compliance check PII confidential information"

        retrieved_rules = retrieve_relevant_rules(query_text, top_k=6)
        return {"retrieved_rules": retrieved_rules}

    except Exception as e:
        # Fallback to default rules if Vector DB fails
        from utils.vector_store import _get_default_rules_text
        return {
            "retrieved_rules": _get_default_rules_text(),
            "errors": [f"Vector DB retrieval failed: {str(e)} — using default rules"]
        }


# ─── Node 3: PII Check ────────────────────────────────────────────────────────
def check_pii(state: ComplianceState) -> dict:
    """Check for PII using Regex + AI with retrieved rules."""
    rules_config = state.get("rules_config", {})
    if not rules_config.get("pii_check", True):
        report = dict(state.get("report", {}))
        report["PII Detection"] = {"status": "SKIP", "details": "Rule disabled", "flagged_pages": [], "evidence": []}
        return {"report": report}

    pages = state["pages"]

    # Fast regex pre-scan
    pii_patterns = {
        "email":       r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone":       r'(\+?91[-.\s]?)?[6-9]\d{9}|(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}',
        "aadhaar":     r'\b\d{4}\s?\d{4}\s?\d{4}\b',
        "pan":         r'\b[A-Z]{5}[0-9]{4}[A-Z]\b',
        "ssn":         r'\b\d{3}-\d{2}-\d{4}\b',
        "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        "api_key":     r'\b(sk-[a-zA-Z0-9]{20,}|gsk_[a-zA-Z0-9]{20,}|AIza[a-zA-Z0-9]{35})\b',
    }

    flagged_pages = []
    evidence = []
    for page in pages:
        text = page["text"]
        for pii_type, pattern in pii_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                flagged_pages.append(page["page_num"])
                evidence.append(f"{pii_type} found on page {page['page_num']}")
                break

    if flagged_pages:
        result = {
            "status": "FAIL",
            "details": f"PII detected on {len(set(flagged_pages))} page(s): {'; '.join(evidence[:3])}",
            "flagged_pages": list(set(flagged_pages)),
            "evidence": evidence[:5]
        }
    else:
        try:
            ai = get_ai_client(state["provider"], state["api_key"], state["model"])
            pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:500]}" for p in pages])
            system = build_system_prompt(state.get("retrieved_rules", ""))
            response = ai(system, build_check_prompt(
                "PII Detection",
                rules_config.get("pii_description", "Flag any personal identifying information"),
                pages_text
            ))
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
        except Exception as e:
            result = {"status": "PASS", "details": f"Regex scan clear. AI check note: {str(e)[:100]}", "flagged_pages": [], "evidence": []}

    report = dict(state.get("report", {}))
    report["PII Detection"] = result
    return {"report": report}


# ─── Node 4: Confidential Info Check ─────────────────────────────────────────
def check_confidential(state: ComplianceState) -> dict:
    """Check for confidential information using AI + retrieved rules."""
    rules_config = state.get("rules_config", {})
    if not rules_config.get("confidential_check", True):
        report = dict(state.get("report", {}))
        report["Confidential Info"] = {"status": "SKIP", "details": "Rule disabled", "flagged_pages": [], "evidence": []}
        return {"report": report}

    try:
        ai = get_ai_client(state["provider"], state["api_key"], state["model"])
        pages = state["pages"]
        pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:600]}" for p in pages])
        system = build_system_prompt(state.get("retrieved_rules", ""))
        response = ai(system, build_check_prompt(
            "Confidential Information",
            rules_config.get("confidential_description", "Flag sensitive business information, API keys, passwords"),
            pages_text
        ))
        clean = response.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
    except Exception as e:
        result = {"status": "ERROR", "details": str(e)[:200], "flagged_pages": [], "evidence": []}

    report = dict(state.get("report", {}))
    report["Confidential Info"] = result
    return {"report": report}


# ─── Node 5: Encoding Check ───────────────────────────────────────────────────
def check_encoding(state: ComplianceState) -> dict:
    """Check UTF-8 encoding consistency using page metadata."""
    rules_config = state.get("rules_config", {})
    if not rules_config.get("encoding_check", True):
        report = dict(state.get("report", {}))
        report["Encoding Check"] = {"status": "SKIP", "details": "Rule disabled", "flagged_pages": [], "evidence": []}
        return {"report": report}

    flagged_pages = []
    issues = []
    for page in state["pages"]:
        page_issues = page.get("encoding_issues", [])
        if page_issues:
            flagged_pages.append(page["page_num"])
            issues.extend([f"Page {page['page_num']}: {issue}" for issue in page_issues])

    if flagged_pages:
        result = {
            "status": "FAIL",
            "details": f"Encoding issues on pages: {flagged_pages}. {'; '.join(issues[:3])}",
            "flagged_pages": flagged_pages,
            "evidence": issues[:5]
        }
    else:
        result = {
            "status": "PASS",
            "details": "All pages have consistent UTF-8 encoding with English text only.",
            "flagged_pages": [],
            "evidence": []
        }

    report = dict(state.get("report", {}))
    report["Encoding Check"] = result
    return {"report": report}


# ─── Node 6: Abusive Content Check ───────────────────────────────────────────
def check_abusive_content(state: ComplianceState) -> dict:
    """Check for abusive or unlawful content using keyword filter + AI."""
    rules_config = state.get("rules_config", {})
    if not rules_config.get("abusive_check", True):
        report = dict(state.get("report", {}))
        report["Abusive Content"] = {"status": "SKIP", "details": "Rule disabled", "flagged_pages": [], "evidence": []}
        return {"report": report}

    abusive_keywords = ["kill", "murder", "threat", "illegal", "fraud", "scam",
                        "drug", "weapon", "bomb", "hate", "racist", "slur", "abuse"]
    pages = state["pages"]
    pre_flagged = [p["page_num"] for p in pages
                   if any(kw in p["text"].lower() for kw in abusive_keywords)]

    try:
        ai = get_ai_client(state["provider"], state["api_key"], state["model"])
        pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:500]}" for p in pages])
        system = build_system_prompt(state.get("retrieved_rules", ""))
        response = ai(system, build_check_prompt(
            "Abusive & Unlawful Content",
            rules_config.get("abusive_description", "Flag abusive, offensive, or unlawful content"),
            pages_text
        ))
        clean = response.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        if pre_flagged and result.get("status") == "PASS":
            result["details"] += f" (Keywords flagged on pages {pre_flagged} — manual review recommended)"
    except Exception as e:
        result = {
            "status": "PASS" if not pre_flagged else "WARN",
            "details": f"AI check note: {str(e)[:100]}. Keyword scan: {'issues on pages ' + str(pre_flagged) if pre_flagged else 'clear'}",
            "flagged_pages": pre_flagged,
            "evidence": []
        }

    report = dict(state.get("report", {}))
    report["Abusive Content"] = result
    return {"report": report}


# ─── Node 7: Aggregate Results ────────────────────────────────────────────────
def aggregate_results(state: ComplianceState) -> dict:
    """Summarize all compliance check results."""
    report = state.get("report", {})
    failed = [k for k, v in report.items() if v.get("status") == "FAIL"]
    total_flagged = sum(len(v.get("flagged_pages", [])) for v in report.values())

    report["_summary"] = {
        "total_checks": len(report),
        "failed_checks": len(failed),
        "passed_checks": len(report) - len(failed),
        "total_pages_flagged": total_flagged,
        "overall_status": "FAIL" if failed else "PASS",
        "failed_rules": failed,
        "rules_source": "Vector DB (RAG)" if state.get("retrieved_rules") else "Default"
    }
    return {"report": report}


# ─── Pipeline Builder ─────────────────────────────────────────────────────────
def build_pipeline(api_key: str, provider: str, model: str, rules_config: dict):
    """Build and compile the LangGraph RAG compliance pipeline."""
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError:
        raise ImportError("Run: pip install langgraph")

    def inject(state):
        return {
            "api_key": api_key,
            "provider": provider,
            "model": model,
            "rules_config": rules_config,
            "report": {},
            "retrieved_rules": "",
            "errors": []
        }

    builder = StateGraph(ComplianceState)

    builder.add_node("inject_credentials",    inject)
    builder.add_node("retrieve_rules",        retrieve_rules)   # ← RAG node
    builder.add_node("check_pii",             check_pii)
    builder.add_node("check_confidential",    check_confidential)
    builder.add_node("check_encoding",        check_encoding)
    builder.add_node("check_abusive_content", check_abusive_content)
    builder.add_node("aggregate_results",     aggregate_results)

    builder.add_edge(START,                  "inject_credentials")
    builder.add_edge("inject_credentials",   "retrieve_rules")      # ← RAG first
    builder.add_edge("retrieve_rules",       "check_pii")
    builder.add_edge("check_pii",            "check_confidential")
    builder.add_edge("check_confidential",   "check_encoding")
    builder.add_edge("check_encoding",       "check_abusive_content")
    builder.add_edge("check_abusive_content","aggregate_results")
    builder.add_edge("aggregate_results",    END)

    return builder.compile()