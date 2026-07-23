from typing import TypedDict, Optional, List, Dict, Any


class IntakeState(TypedDict, total=False):
    # input
    source_text: str
    existing_complaints: List[Dict[str, Any]]  # lightweight records used for duplicate detection

    # produced by nodes, in pipeline order
    extracted: Dict[str, Any]
    completeness: Dict[str, Any]
    risk_classification: str
    duplicate_of: Optional[str]
    duplicate_reason: Optional[str]
    summary: str
    root_cause: str
    capa: str
