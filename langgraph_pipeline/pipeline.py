"""
LangGraph Compliance Pipeline
Orchestrates multi-step compliance checking using a stateful graph.

Flow:
  START → extract_pages → [pii_check, confidential_check, encoding_check, abuse_check] → aggregate_results → END
"""
from typing import TypedDict, Annotated, Any
import json
import re
import operator


# ─── State Definition ─────────────────────────────────────────────────────────
class ComplianceState(TypedDict):
    pages: list[dict]
    filename: str
    rules: dict
    api_key: str
    provider: str
    model: str
    report: dict
    errors: Annotated[list[str], operator.add]


# ─── AI Client Factory ────────────────────────────────────────────────────────
def get_ai_client(provider: str, api_key: str, model: str):
    """Returns a callable that takes (system_prompt, user_prompt) -> str."""

    if "Groq" in provider:
        from groq import Groq
        client = Groq(api_key=api_key)

        def call(system: str, user: str) -> str:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
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
            message = client.messages.create(
                model=model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user}]
            )
            return message.content[0].text

        return call

    elif "Google" in provider:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gmodel = genai.GenerativeModel(model)

        def call(system: str, user: str) -> str:
            response = gmodel.generate_content(f"{system}\n\n{user}")
            return response.text

        return call

    elif "OpenAI" in provider:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        def call(system: str, user: str) -> str:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                temperature=0.1,
                max_tokens=2048
            )
            return response.choices[0].message.content

        return call

    else:
        raise ValueError(f"Unknown provider: {provider}")


# ─── Prompt Builder ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a document compliance auditor. Your job is to analyze document text and identify compliance violations.

Always respond ONLY with valid JSON in exactly this format:
{
  "status": "PASS" or "FAIL",
  "details": "Brief explanation of findings",
  "flagged_pages": [list of page numbers with issues, e.g. [1, 3]],
  "evidence": ["list of specific problematic snippets found (max 5)"]
}

Be precise and conservative. Only flag clear violations, not ambiguous content."""


def build_check_prompt(check_type: str, description: str, pages_text: str) -> str:
    return f"""
COMPLIANCE CHECK: {check_type}
RULE: {description}

Analyze the following document text page-by-page and determine if this compliance rule is violated.

DOCUMENT CONTENT:
{pages_text[:8000]}

Respond with JSON only as specified.
"""


# ─── Pipeline Nodes ───────────────────────────────────────────────────────────
def check_pii(state: ComplianceState) -> dict:
    """Check for PII: emails, phone numbers, SSNs, credit cards."""
    rules = state["rules"]
    if not rules.get("pii_check", True):
        return {"report": {**state.get("report", {}), "PII Detection": {"status": "SKIP", "details": "Rule disabled", "flagged_pages": []}}}

    # First do a fast regex check
    pages = state["pages"]
    pii_patterns = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}',
        "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    }

    flagged_pages = []
    evidence = []
    for page in pages:
        text = page["text"]
        for pii_type, pattern in pii_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                flagged_pages.append(page["page_num"])
                evidence.append(f"{pii_type}: found on page {page['page_num']}")
                break

    if flagged_pages:
        result = {
            "status": "FAIL",
            "details": f"PII detected on {len(set(flagged_pages))} page(s): {', '.join(evidence[:3])}",
            "flagged_pages": list(set(flagged_pages)),
            "evidence": evidence[:5]
        }
    else:
        # Use AI for deeper check
        try:
            ai = get_ai_client(state["provider"], state["api_key"], state["model"])
            pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:500]}" for p in pages])
            response = ai(SYSTEM_PROMPT, build_check_prompt(
                "PII Detection",
                rules.get("pii_description", "Flag any personal information"),
                pages_text
            ))
            result = json.loads(response.strip())
        except Exception as e:
            result = {"status": "PASS", "details": f"Regex scan clear. AI check skipped: {str(e)}", "flagged_pages": [], "evidence": []}

    report = dict(state.get("report", {}))
    report["PII Detection"] = result
    return {"report": report}


def check_confidential(state: ComplianceState) -> dict:
    """Check for confidential information using AI."""
    rules = state["rules"]
    if not rules.get("confidential_check", True):
        return {"report": {**state.get("report", {}), "Confidential Info": {"status": "SKIP", "details": "Rule disabled", "flagged_pages": []}}}

    try:
        ai = get_ai_client(state["provider"], state["api_key"], state["model"])
        pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:600]}" for p in state["pages"]])
        response = ai(SYSTEM_PROMPT, build_check_prompt(
            "Confidential Information",
            rules.get("confidential_description", "Flag sensitive company information"),
            pages_text
        ))
        result = json.loads(response.strip())
    except Exception as e:
        result = {"status": "ERROR", "details": str(e), "flagged_pages": [], "evidence": []}

    report = dict(state.get("report", {}))
    report["Confidential Info"] = result
    return {"report": report}


def check_encoding(state: ComplianceState) -> dict:
    """Check UTF-8 encoding consistency using regex + page metadata."""
    rules = state["rules"]
    if not rules.get("encoding_check", True):
        return {"report": {**state.get("report", {}), "Encoding Check": {"status": "SKIP", "details": "Rule disabled", "flagged_pages": []}}}

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
            "details": "All pages appear to have consistent UTF-8 encoding with English text only.",
            "flagged_pages": [],
            "evidence": []
        }

    report = dict(state.get("report", {}))
    report["Encoding Check"] = result
    return {"report": report}


def check_abusive_content(state: ComplianceState) -> dict:
    """Check for abusive, offensive or unlawful content using AI."""
    rules = state["rules"]
    if not rules.get("abusive_check", True):
        return {"report": {**state.get("report", {}), "Abusive Content": {"status": "SKIP", "details": "Rule disabled", "flagged_pages": []}}}

    # Quick keyword pre-filter
    abusive_keywords = [
        "kill", "murder", "threat", "illegal", "fraud", "scam",
        "drug", "weapon", "bomb", "hate", "racist", "slur"
    ]
    pages = state["pages"]
    pre_flagged = []
    for page in pages:
        text = page["text"].lower()
        if any(kw in text for kw in abusive_keywords):
            pre_flagged.append(page["page_num"])

    try:
        ai = get_ai_client(state["provider"], state["api_key"], state["model"])
        pages_text = "\n\n".join([f"[PAGE {p['page_num']}]\n{p['text'][:500]}" for p in pages])
        response = ai(SYSTEM_PROMPT, build_check_prompt(
            "Abusive & Unlawful Content",
            rules.get("abusive_description", "Flag abusive, offensive, or unlawful content"),
            pages_text
        ))
        result = json.loads(response.strip())
        if pre_flagged and result["status"] == "PASS":
            result["details"] += f" (Note: keywords flagged on pages {pre_flagged} for manual review)"
    except Exception as e:
        result = {
            "status": "PASS" if not pre_flagged else "WARN",
            "details": f"AI check failed: {str(e)}. Keyword scan: {'issues found' if pre_flagged else 'clear'}",
            "flagged_pages": pre_flagged,
            "evidence": []
        }

    report = dict(state.get("report", {}))
    report["Abusive Content"] = result
    return {"report": report}


def aggregate_results(state: ComplianceState) -> dict:
    """Summarize overall compliance status."""
    report = state.get("report", {})
    failed = [k for k, v in report.items() if v.get("status") == "FAIL"]
    total_pages_flagged = sum(len(v.get("flagged_pages", [])) for v in report.values())

    report["_summary"] = {
        "total_checks": len(report),
        "failed_checks": len(failed),
        "passed_checks": len(report) - len(failed),
        "total_pages_flagged": total_pages_flagged,
        "overall_status": "FAIL" if failed else "PASS",
        "failed_rules": failed
    }

    return {"report": report}


# ─── Pipeline Builder ─────────────────────────────────────────────────────────
def build_pipeline(api_key: str, provider: str, model: str, rules: dict):
    """Build and compile the LangGraph compliance pipeline."""
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError:
        raise ImportError("LangGraph not installed. Run: pip install langgraph")

    # Inject credentials into state via closure
    def inject_credentials(state: ComplianceState) -> dict:
        return {
            "api_key": api_key,
            "provider": provider,
            "model": model,
            "report": {}
        }

    builder = StateGraph(ComplianceState)

    # Add nodes
    builder.add_node("inject_credentials", inject_credentials)
    builder.add_node("check_pii", check_pii)
    builder.add_node("check_confidential", check_confidential)
    builder.add_node("check_encoding", check_encoding)
    builder.add_node("check_abusive_content", check_abusive_content)
    builder.add_node("aggregate_results", aggregate_results)

    # Define edges: sequential for simplicity (can be parallelized with Send API)
    builder.add_edge(START, "inject_credentials")
    builder.add_edge("inject_credentials", "check_pii")
    builder.add_edge("check_pii", "check_confidential")
    builder.add_edge("check_confidential", "check_encoding")
    builder.add_edge("check_encoding", "check_abusive_content")
    builder.add_edge("check_abusive_content", "aggregate_results")
    builder.add_edge("aggregate_results", END)

    return builder.compile()