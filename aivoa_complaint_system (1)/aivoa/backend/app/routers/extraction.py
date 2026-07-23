from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.agents.graph import intake_graph
from app.utils.document_parser import extract_text, SUPPORTED_EXTENSIONS
from app.config import get_settings

router = APIRouter(prefix="/api/extract", tags=["extraction"])
settings = get_settings()


def _run_pipeline(text: str, db: Session) -> schemas.ExtractResponse:
    # Lightweight snapshot of existing complaints for duplicate detection
    existing = [
        {
            "id": c.id,
            "product_name": c.product_name,
            "batch_lot_number": c.batch_lot_number,
            "detailed_description": c.detailed_description,
        }
        for c in db.query(models.Complaint).order_by(models.Complaint.created_at.desc()).limit(50).all()
    ]

    result = intake_graph.invoke({"source_text": text, "existing_complaints": existing})

    extracted = result.get("extracted", {}) or {}
    return schemas.ExtractResponse(
        extracted=schemas.ComplaintBase(**{k: v for k, v in extracted.items() if k in schemas.ComplaintBase.model_fields}),
        completeness=result.get("completeness", {}),
        risk_classification=result.get("risk_classification"),
        duplicate_of=result.get("duplicate_of"),
        duplicate_reason=result.get("duplicate_reason"),
        summary=result.get("summary"),
        root_cause=result.get("root_cause"),
        capa=result.get("capa"),
        source_text=text,
    ), result


@router.post("/text", response_model=schemas.ExtractResponse)
def extract_from_text(payload: schemas.ExtractRequest, db: Session = Depends(get_db)):
    if not payload.text.strip():
        raise HTTPException(400, "No text provided")
    response, _full_state = _run_pipeline(payload.text, db)
    return response


@router.post("/file", response_model=schemas.ExtractResponse)
async def extract_from_file(file: UploadFile = File(...), session_id: str = Form(...), db: Session = Depends(get_db)):
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {settings.MAX_UPLOAD_MB}MB limit")

    text = extract_text(file.filename, content)
    if not text.strip():
        raise HTTPException(422, "Could not extract any text from the document")

    response, _full_state = _run_pipeline(text, db)
    return response
