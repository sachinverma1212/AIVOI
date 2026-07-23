import uuid
import datetime as dt

from sqlalchemy import Column, String, Text, DateTime, Float, JSON
from app.database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Complaint(Base):
    """
    Maps 1:1 to the 'Log Customer Complaint' form shown in the reference UI.
    Section 1: Origin & Customer Details
    Section 2: Product & Batch Identification
    Section 3: Complaint Details
    Section 4: Initial Assessment & Priority
    """
    __tablename__ = "complaints"

    id = Column(String(36), primary_key=True, default=gen_id)

    # 1. Origin & Customer Details
    complaint_source = Column(String(120))       # Email / Phone / Portal / Field Rep ...
    customer_name = Column(String(200))

    # 2. Product & Batch Identification
    product_name = Column(String(200))
    product_strength_grade = Column(String(120))
    batch_lot_number = Column(String(120))
    manufacturing_date = Column(String(40))
    expiry_date = Column(String(40))
    quantity_affected = Column(String(60))

    # 3. Complaint Details
    complaint_type = Column(String(120))         # e.g. Quality Deviation, Adverse Event, Packaging Defect
    complaint_date = Column(String(40))
    detailed_description = Column(Text)

    # 4. Initial Assessment & Priority
    initial_severity = Column(String(40))         # Minor / Major / Critical
    priority = Column(String(40))                 # Low / Medium / High / Urgent
    status = Column(String(40), default="Pending Triage")

    # Raw source text/document this record was extracted from (for audit + duplicate detection)
    source_text = Column(Text)

    # Bonus AI outputs, stored so the UI can render them without recomputation
    ai_summary = Column(Text)
    ai_root_cause = Column(Text)
    ai_capa = Column(Text)
    ai_risk_classification = Column(String(40))
    ai_completeness = Column(JSON)   # {"missing_fields": [...], "is_complete": bool, "notes": "..."}
    ai_duplicate_of = Column(String(36), nullable=True)  # complaint id, if flagged as duplicate

    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class ChatMessage(Base):
    """Conversation history for the AI Complaint Intake Assistant, scoped per complaint (or per session)."""
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=gen_id)
    session_id = Column(String(64), index=True)        # groups messages for one intake session
    complaint_id = Column(String(36), nullable=True)    # linked once a complaint is saved
    role = Column(String(20))                           # user | assistant
    content = Column(Text)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
