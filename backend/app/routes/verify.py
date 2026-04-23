"""
Public verification endpoint — NO AUTH.

A buyer in Amsterdam holds a signed sustainability PDF from a Tiruppur
factory. They land on https://<greenthread>/verify/<report_id>, which calls
GET /api/verify/{report_id}. We return:

  - the factory name and location (so they know what they're looking at),
  - the public key the report was signed with,
  - the signature,
  - the payload hash,
  - a fresh cryptographic verification result (computed server-side so the
    UI can show a green tick without the buyer running crypto),
  - the Merkle anchor reference (once the daily job has run),
  - any OpenTimestamps proof that has been upgraded with a Bitcoin attestation.

Intentionally sparse — we never return the raw payload or the PDF from this
endpoint to avoid leaking factory-internal data to anyone who guesses a
report id. The buyer already has the PDF; they're here to verify it.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session
from fastapi import Depends

from ..database import get_db
from ..models import Report
from ..services.signing_service import SigningError, verify_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verify", tags=["Verify"])


@router.get("/{report_id}")
async def verify_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    factory = report.factory
    signature = report.signature
    anchor = report.merkle_anchor

    response: dict = {
        "report_id": report.id,
        "report_type": report.report_type.value if report.report_type else None,
        "date_from": report.date_from,
        "date_to": report.date_to,
        "created_at": report.created_at,
        "factory": {
            "name": factory.name if factory else None,
            "location": factory.location if factory else None,
        },
        "payload_hash": report.payload_hash,
        "signature": None,
        "signature_valid": False,
        "merkle_anchor": None,
    }

    if signature:
        response["signature"] = {
            "algorithm": signature.algorithm,
            "provider": signature.provider.value,
            "signed_at": signature.signed_at,
            "signature_b64": signature.signature_b64,
            "public_key_pem": signature.public_key_pem,
        }
        if report.payload_hash:
            try:
                response["signature_valid"] = verify_signature(
                    public_key_pem=signature.public_key_pem,
                    algorithm=signature.algorithm,
                    signature_b64=signature.signature_b64,
                    payload_hash_hex=report.payload_hash,
                )
            except SigningError as err:
                logger.warning("verify failed for report=%s: %s", report_id, err)
                response["signature_valid"] = False

    if anchor:
        proofs = anchor.inclusion_proofs or {}
        response["merkle_anchor"] = {
            "anchor_date": anchor.anchor_date,
            "merkle_root_hex": anchor.merkle_root_hex,
            "leaf_count": anchor.leaf_count,
            "inclusion_proof": proofs.get(report.payload_hash or ""),
            "ots_submitted_at": anchor.ots_submitted_at,
            "ots_upgraded_at": anchor.ots_upgraded_at,
            "ots_proof_available": bool(anchor.ots_proof_hex),
        }

    return response
