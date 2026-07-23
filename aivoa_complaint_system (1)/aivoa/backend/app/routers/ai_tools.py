from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.agents import nodes

router = APIRouter(prefix="/api/ai", tags=["ai-tools"])


def _complaint_to_extracted_dict(c: models.Complaint) -> dict:
    return {
        "complaint_source": c.complaint_source,
        "customer_name": c.customer_name,
        "product_name": c.product_name,
        "product_strength_grade": c.product_strength_grade,
        "batch_lot_number": c.batch_lot_number,
        "manufacturing_date": c.manufacturing_date,
        "expiry_date": c.expiry_date,
        "quantity_affected": c.quantity_affected,
        "complaint_type": c.complaint_type,
        "complaint_date": c.complaint_date,
        "detailed_description": c.detailed_description,
        "initial_severity": c.initial_severity,
        "priority": c.priority,
    }


def _get_complaint(db: Session, complaint_id: str) -> models.Complaint:
    complaint = db.query(models.Complaint).get(complaint_id)
    if not complaint:
        raise HTTPException(404, "Complaint not found")
    return complaint


@router.post("/summary", response_model=schemas.ComplaintOut)
def regenerate_summary(payload: schemas.BonusRequest, db: Session = Depends(get_db)):
    complaint = _get_complaint(db, payload.complaint_id)
    state = nodes.summary_node({"extracted": _complaint_to_extracted_dict(complaint)})
    complaint.ai_summary = state["summary"]
    db.commit()
    db.refresh(complaint)
    return complaint


@router.post("/root-cause", response_model=schemas.ComplaintOut)
def regenerate_root_cause(payload: schemas.BonusRequest, db: Session = Depends(get_db)):
    complaint = _get_complaint(db, payload.complaint_id)
    state = nodes.root_cause_node({"extracted": _complaint_to_extracted_dict(complaint)})
    complaint.ai_root_cause = state["root_cause"]
    db.commit()
    db.refresh(complaint)
    return complaint


@router.post("/capa", response_model=schemas.ComplaintOut)
def regenerate_capa(payload: schemas.BonusRequest, db: Session = Depends(get_db)):
    complaint = _get_complaint(db, payload.complaint_id)
    extracted = _complaint_to_extracted_dict(complaint)
    rc_state = nodes.root_cause_node({"extracted": extracted})
    capa_state = nodes.capa_node({"extracted": extracted, "root_cause": rc_state["root_cause"]})
    complaint.ai_root_cause = rc_state["root_cause"]
    complaint.ai_capa = capa_state["capa"]
    db.commit()
    db.refresh(complaint)
    return complaint


@router.post("/risk", response_model=schemas.ComplaintOut)
def regenerate_risk(payload: schemas.BonusRequest, db: Session = Depends(get_db)):
    complaint = _get_complaint(db, payload.complaint_id)
    state = nodes.risk_node({"extracted": _complaint_to_extracted_dict(complaint)})
    complaint.ai_risk_classification = state["risk_classification"]
    complaint.initial_severity = state["extracted"].get("initial_severity", complaint.initial_severity)
    complaint.priority = state["extracted"].get("priority", complaint.priority)
    db.commit()
    db.refresh(complaint)
    return complaint


@router.post("/duplicate-check", response_model=schemas.ComplaintOut)
def check_duplicate(payload: schemas.BonusRequest, db: Session = Depends(get_db)):
    complaint = _get_complaint(db, payload.complaint_id)
    others = [
        {
            "id": c.id,
            "product_name": c.product_name,
            "batch_lot_number": c.batch_lot_number,
            "detailed_description": c.detailed_description,
        }
        for c in db.query(models.Complaint).filter(models.Complaint.id != complaint.id).limit(50).all()
    ]
    state = nodes.duplicate_node({
        "extracted": _complaint_to_extracted_dict(complaint),
        "existing_complaints": others,
    })
    complaint.ai_duplicate_of = state.get("duplicate_of")
    db.commit()
    db.refresh(complaint)
    return complaint
