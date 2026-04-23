"""
POST /api/ocr/extract — assist-only OCR endpoint.

Accepts a multipart file (image/pdf) plus a hint for the kind of document,
runs it through Anthropic's vision API, and returns structured fields for the
caller to show in a confirmation dialog before persisting.

This is explicitly *not* a write endpoint — we never create a
ProductionRecord, Chemical or similar from the raw OCR output. The user
reviews & edits first, then posts to the usual CRUD endpoints.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from ..models import User
from ..services.ocr_service import (
    SUPPORTED_MEDIA,
    OcrServiceError,
    extract_from_image,
)
from ..utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr", tags=["OCR"])


# Cap file size so we don't send a 50 MB scan to Claude. 10 MB is plenty for
# a phone photo of a bill.
_MAX_FILE_BYTES = 10 * 1024 * 1024

_VALID_HINTS = {"electricity_bill", "water_bill", "dye_invoice", "fabric_invoice"}


@router.post("/extract")
async def extract(
    file: UploadFile = File(...),
    hint: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    """Extract structured fields from a bill/invoice image or PDF."""
    if hint not in _VALID_HINTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid hint — must be one of {sorted(_VALID_HINTS)}",
        )

    media_type = (file.content_type or "").lower()
    if media_type not in SUPPORTED_MEDIA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported content-type {media_type!r}; accepted: {sorted(SUPPORTED_MEDIA)}",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="empty file upload",
        )
    if len(raw) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file too large ({len(raw)} bytes); limit is {_MAX_FILE_BYTES}",
        )

    try:
        result = extract_from_image(raw, media_type, hint)  # type: ignore[arg-type]
    except OcrServiceError as err:
        logger.warning("ocr.extract failed: %s", err)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"OCR failed: {err}",
        ) from err
    except Exception:
        logger.exception("ocr.extract unexpected error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR failed unexpectedly",
        )

    return {
        "hint": hint,
        "filename": file.filename,
        "content_type": media_type,
        "size_bytes": len(raw),
        **result.to_dict(),
    }
