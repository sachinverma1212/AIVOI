from typing import Optional, List
from pydantic import BaseModel


class ComplaintBase(BaseModel):
    complaint_source: Optional[str] = None
    customer_name: Optional[str] = None
    product_name: Optional[str] = None
    product_strength_grade: Optional[str] = None
    batch_lot_number: Optional[str] = None
    manufacturing_date: Optional[str] = None
    expiry_date: Optional[str] = None
    quantity_affected: Optional[str] = None
    complaint_type: Optional[str] = None
    complaint_date: Optional[str] = None
    detailed_description: Optional[str] = None
    initial_severity: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = "Pending Triage"


class ComplaintCreate(ComplaintBase):
    source_text: Optional[str] = None


class ComplaintUpdate(ComplaintBase):
    pass


class ComplaintOut(ComplaintBase):
    id: str
    ai_summary: Optional[str] = None
    ai_root_cause: Optional[str] = None
    ai_capa: Optional[str] = None
    ai_risk_classification: Optional[str] = None
    ai_completeness: Optional[dict] = None
    ai_duplicate_of: Optional[str] = None

    class Config:
        from_attributes = True


class ExtractRequest(BaseModel):
    text: str
    session_id: str


class ExtractResponse(BaseModel):
    extracted: ComplaintBase
    completeness: dict
    risk_classification: Optional[str] = None
    duplicate_of: Optional[str] = None
    duplicate_reason: Optional[str] = None
    summary: Optional[str] = None
    root_cause: Optional[str] = None
    capa: Optional[str] = None
    source_text: Optional[str] = None



class ChatRequest(BaseModel):
    session_id: str
    message: str
    complaint_id: Optional[str] = None
    # Current in-progress form state, so the assistant can answer
    # "what's the batch number?" even before the complaint is saved.
    context: Optional[dict] = None


class ChatMessageOut(BaseModel):
    role: str
    content: str

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    reply: str
    history: List[ChatMessageOut]


class BonusRequest(BaseModel):
    complaint_id: str
