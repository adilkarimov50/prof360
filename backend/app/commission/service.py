"""Фоновый пайплайн анализа документов комиссии."""
from __future__ import annotations

import logging
import os

from app.commission import analyzer, extract
from app.core.audit import log_action
from app.core.db import SessionLocal
from app.models.commission import CommissionDocument

logger = logging.getLogger("prof360.commission")

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")


def ensure_upload_dir() -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    return UPLOAD_DIR


def run_analysis(document_id: int, *, username: str | None = None) -> None:
    """Извлечение текста + двухэтапный анализ (вызывается из фоновой задачи)."""
    db = SessionLocal()
    doc = db.query(CommissionDocument).filter(CommissionDocument.id == document_id).first()
    if not doc:
        db.close()
        return

    path = os.path.join(UPLOAD_DIR, doc.stored_name)
    try:
        doc.status = "analyzing"
        doc.error_message = None
        db.commit()

        if not os.path.isfile(path):
            raise FileNotFoundError("Файл документа не найден на диске")

        with open(path, "rb") as fh:
            file_bytes = fh.read()

        text = extract.extract_text(file_bytes, doc.mime_type, doc.original_filename)
        doc.extracted_text = text

        stage1, stage2, stage_legal, quality, effectiveness, legal_score, recommendation = analyzer.analyze_document(
            db,
            doc_type=doc.doc_type,
            district=doc.district,
            period=doc.period,
            text=text,
            file_bytes=file_bytes if doc.mime_type in ("application/pdf", "image/jpeg", "image/png", "image/jpg") else None,
            mime_type=doc.mime_type,
        )

        doc.analysis_document = stage1
        doc.analysis_execution = stage2
        doc.analysis_legal = stage_legal
        doc.quality_score = quality
        doc.effectiveness_score = effectiveness
        doc.legal_compliance_score = legal_score
        doc.include_recommendation = recommendation
        doc.status = "analyzed"
        db.commit()

        log_action(
            db,
            action="commission_analyze",
            entity_type="commission_document",
            entity_id=doc.id,
            details={
                "username": username,
                "district": doc.district,
                "doc_type": doc.doc_type,
                "quality_score": quality,
                "effectiveness_score": effectiveness,
                "legal_compliance_score": legal_score,
                "violations_count": (stage_legal or {}).get("violations_count"),
                "include_recommendation": recommendation,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Commission analysis failed for doc %s", document_id)
        doc.status = "error"
        doc.error_message = str(exc)[:2000]
        db.commit()
    finally:
        db.close()
