"""
Each function is a LangGraph node. They read from and write to the shared
IntakeState dict. Kept side-effect free (no DB access) so the graph can be
unit tested and reused from both the extraction endpoint and any batch job.
"""
import logging

from app.agents.llm import chat_completion, chat_completion_json
from app.agents.state import IntakeState
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("aivoa.nodes")

REQUIRED_FIELDS = [
    "complaint_source", "customer_name", "product_name", "batch_lot_number",
    "complaint_type", "complaint_date", "detailed_description",
]

FORM_SCHEMA_HINT = """
{
  "complaint_source": "Email | Phone | Customer Portal | Field Representative | Distributor | Other",
  "customer_name": "string",
  "product_name": "string",
  "product_strength_grade": "string, e.g. 500mg tablets",
  "batch_lot_number": "string",
  "manufacturing_date": "YYYY-MM-DD or empty string",
  "expiry_date": "YYYY-MM-DD or empty string",
  "quantity_affected": "string, include unit e.g. '120 kg' or '3 cartons'",
  "complaint_type": "Quality Deviation | Adverse Event | Packaging Defect | Efficacy Issue | Contamination | Labeling Error | Other",
  "complaint_date": "YYYY-MM-DD or empty string",
  "detailed_description": "string, a clear plain-language restatement of the complaint",
  "initial_severity": "Minor | Major | Critical",
  "priority": "Low | Medium | High | Urgent"
}
"""


# ---------------------------------------------------------------------------
# Node 1: Extraction
# ---------------------------------------------------------------------------
def extract_node(state: IntakeState) -> IntakeState:
    """Extract structured complaint fields from raw text (email/PDF/manual paste)."""
    text = state.get("source_text", "").strip()
    if not text:
        state["extracted"] = {}
        return state

    messages = [
        {
            "role": "system",
            "content": (
                "You are a document-extraction assistant for a pharmaceutical Quality "
                "Management System (QMS) Customer Complaint module. Extract the fields "
                "below from the complaint text. If a field is not mentioned, return an "
                "empty string for it — never invent data. Respond with ONLY a JSON object "
                f"matching this schema:\n{FORM_SCHEMA_HINT}"
            ),
        },
        {"role": "user", "content": f"Complaint text:\n\"\"\"\n{text}\n\"\"\""},
    ]
    data = chat_completion_json(messages, model=settings.GROQ_EXTRACTION_MODEL)
    state["extracted"] = data
    return state


# ---------------------------------------------------------------------------
# Node 2: Completeness checker (bonus)
# ---------------------------------------------------------------------------
def completeness_node(state: IntakeState) -> IntakeState:
    extracted = state.get("extracted", {}) or {}
    missing = [f for f in REQUIRED_FIELDS if not str(extracted.get(f, "")).strip()]
    state["completeness"] = {
        "is_complete": len(missing) == 0,
        "missing_fields": missing,
        "notes": (
            "All mandatory fields captured."
            if not missing
            else f"Missing {len(missing)} mandatory field(s): {', '.join(missing)}. "
                 "Ask the reporter for these before triage."
        ),
    }
    return state


# ---------------------------------------------------------------------------
# Node 3: AI risk classification (bonus) — refines/validates severity & priority
# ---------------------------------------------------------------------------
def risk_node(state: IntakeState) -> IntakeState:
    extracted = state.get("extracted", {}) or {}
    description = extracted.get("detailed_description", "")
    complaint_type = extracted.get("complaint_type", "")

    if not description and not complaint_type:
        state["risk_classification"] = extracted.get("initial_severity", "") or "Minor"
        return state

    messages = [
        {
            "role": "system",
            "content": (
                "You classify pharmaceutical customer complaints for a QMS. Consider patient "
                "safety impact, GMP/regulatory implications, and scale (single unit vs whole "
                "batch). Respond with ONLY a JSON object: "
                '{"severity": "Minor|Major|Critical", "priority": "Low|Medium|High|Urgent", '
                '"rationale": "one sentence"}'
            ),
        },
        {
            "role": "user",
            "content": f"Complaint type: {complaint_type}\nDescription: {description}",
        },
    ]
    result = chat_completion_json(messages, model=settings.GROQ_REASONING_MODEL)
    severity = result.get("severity") or extracted.get("initial_severity") or "Minor"
    priority = result.get("priority") or extracted.get("priority") or "Medium"

    # Feed the AI's judgment back into the extracted fields shown on the form
    extracted["initial_severity"] = severity
    extracted["priority"] = priority
    state["extracted"] = extracted
    state["risk_classification"] = f"{severity} / {priority} — {result.get('rationale', '')}".strip(" —")
    return state


# ---------------------------------------------------------------------------
# Node 4: Duplicate complaint detection (bonus)
# ---------------------------------------------------------------------------
def duplicate_node(state: IntakeState) -> IntakeState:
    extracted = state.get("extracted", {}) or {}
    candidates = state.get("existing_complaints", []) or []

    if not candidates:
        state["duplicate_of"] = None
        state["duplicate_reason"] = None
        return state

    # Narrow candidates cheaply first (same product or same batch), then let the LLM
    # make the final call so we don't pay for a full LLM pass over every record.
    narrowed = [
        c for c in candidates
        if (c.get("product_name") and c.get("product_name") == extracted.get("product_name"))
        or (c.get("batch_lot_number") and c.get("batch_lot_number") == extracted.get("batch_lot_number"))
    ] or candidates[:10]

    messages = [
        {
            "role": "system",
            "content": (
                "You detect duplicate/related pharmaceutical customer complaints. Given a NEW "
                "complaint and a list of EXISTING complaints (id + summary fields), decide if "
                "the new one is very likely the same underlying issue as an existing one "
                "(same product/batch and same defect description, even if worded differently). "
                'Respond with ONLY JSON: {"duplicate_id": "<id or empty string>", "reason": "one sentence or empty string"}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"NEW complaint: {extracted}\n\nEXISTING complaints:\n"
                + "\n".join(f"- id={c.get('id')}: {c}" for c in narrowed)
            ),
        },
    ]
    result = chat_completion_json(messages, model=settings.GROQ_REASONING_MODEL)
    dup_id = (result.get("duplicate_id") or "").strip()
    state["duplicate_of"] = dup_id or None
    state["duplicate_reason"] = result.get("reason") or None
    return state


# ---------------------------------------------------------------------------
# Node 5: Summary (bonus)
# ---------------------------------------------------------------------------
def summary_node(state: IntakeState) -> IntakeState:
    extracted = state.get("extracted", {}) or {}
    messages = [
        {"role": "system", "content": "Summarize the pharmaceutical complaint in 2-3 concise sentences for a QA reviewer."},
        {"role": "user", "content": str(extracted)},
    ]
    state["summary"] = chat_completion(messages, model=settings.GROQ_REASONING_MODEL, max_tokens=200)
    return state


# ---------------------------------------------------------------------------
# Node 6: Root cause recommendation (bonus)
# ---------------------------------------------------------------------------
def root_cause_node(state: IntakeState) -> IntakeState:
    extracted = state.get("extracted", {}) or {}
    messages = [
        {
            "role": "system",
            "content": (
                "You are a QA investigator for an API/FDF pharmaceutical manufacturer. "
                "Given a customer complaint, list the 2-4 most likely root cause categories "
                "(e.g. raw material variability, equipment malfunction, process deviation, "
                "storage/transport condition, labeling/packaging error, operator error) with a "
                "one-line justification each. Be concise, bullet points only."
            ),
        },
        {"role": "user", "content": str(extracted)},
    ]
    state["root_cause"] = chat_completion(messages, model=settings.GROQ_REASONING_MODEL, max_tokens=300)
    return state


# ---------------------------------------------------------------------------
# Node 7: CAPA recommendation (bonus)
# ---------------------------------------------------------------------------
def capa_node(state: IntakeState) -> IntakeState:
    extracted = state.get("extracted", {}) or {}
    root_cause = state.get("root_cause", "")
    messages = [
        {
            "role": "system",
            "content": (
                "You recommend draft Corrective and Preventive Actions (CAPA) for a "
                "pharmaceutical QMS complaint, aligned to the likely root cause. Give short, "
                "actionable bullet points split into 'Corrective:' and 'Preventive:' sections."
            ),
        },
        {"role": "user", "content": f"Complaint: {extracted}\nLikely root cause(s): {root_cause}"},
    ]
    state["capa"] = chat_completion(messages, model=settings.GROQ_REASONING_MODEL, max_tokens=300)
    return state
