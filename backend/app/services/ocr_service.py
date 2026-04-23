"""
OCR service — extracts structured values from utility bills, dye/fabric invoices
using Anthropic Claude's vision API.

Why Claude vision (vs. Tesseract/Textract): utility bills in Tiruppur are messy,
bilingual (Tamil + English), often photos taken with a phone under bad light.
A VLM with a specific schema + "hint" for what kind of document it is handles
this far better than OCR-then-regex. It also returns JSON directly, skipping a
brittle parsing step.

Inputs:
  - base64-encoded image (jpeg/png/webp) or PDF
  - hint: one of ELECTRICITY_BILL, WATER_BILL, DYE_INVOICE, FABRIC_INVOICE

Output (always): { fields: {...}, confidence: 0-1, notes: str, raw_model_text: str }

The caller is expected to present the extracted fields back to the user for
confirmation before persisting — OCR is an assist, not an oracle.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Literal, Optional

logger = logging.getLogger(__name__)


OcrHint = Literal[
    "electricity_bill",
    "water_bill",
    "dye_invoice",
    "fabric_invoice",
]

SUPPORTED_MEDIA = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}


# Per-hint instructions: what fields to pull out, in what shape.
# Keep the shapes simple and flat so the frontend can bind to form inputs
# one-for-one.
_HINT_INSTRUCTIONS: dict[str, str] = {
    "electricity_bill": (
        "This is an Indian electricity utility bill (likely TANGEDCO / TNEB for "
        "Tamil Nadu). Extract:\n"
        "  - consumer_number (string)\n"
        "  - bill_period_from (ISO date, YYYY-MM-DD)\n"
        "  - bill_period_to   (ISO date, YYYY-MM-DD)\n"
        "  - units_consumed_kwh (number; also called 'units' or 'kWh')\n"
        "  - amount_inr (number)\n"
        "  - tariff_category (string, e.g. 'LT-III' / 'HT')\n"
        "If a field is not present on the bill, set it to null."
    ),
    "water_bill": (
        "This is an Indian water supply / metered water bill. Extract:\n"
        "  - consumer_number (string)\n"
        "  - bill_period_from (ISO date)\n"
        "  - bill_period_to   (ISO date)\n"
        "  - water_consumed_kl (number; 1 kL = 1000 L — convert if the bill is in litres)\n"
        "  - amount_inr (number)\n"
        "If a field is not present, null."
    ),
    "dye_invoice": (
        "This is a dye / chemical supplier invoice (Tiruppur textile context).\n"
        "Extract a flat summary plus a line-items array:\n"
        "  - supplier_name (string)\n"
        "  - invoice_number (string)\n"
        "  - invoice_date (ISO date)\n"
        "  - total_amount_inr (number)\n"
        "  - items: array of { chemical_name, cas_number (or null), quantity_kg, unit_price_inr }\n"
        "CAS numbers look like 1234-56-7. Leave null if not printed."
    ),
    "fabric_invoice": (
        "This is a fabric / yarn purchase invoice. Extract:\n"
        "  - supplier_name (string)\n"
        "  - invoice_number (string)\n"
        "  - invoice_date (ISO date)\n"
        "  - total_amount_inr (number)\n"
        "  - items: array of { fabric_type ('cotton' | 'polyester' | 'blend' | other), "
        "quantity_kg, unit_price_inr }\n"
        "Normalise fabric_type to lowercase; if a blend, use 'blend'."
    ),
}


@dataclass
class OcrResult:
    fields: dict
    confidence: float
    notes: str
    raw_model_text: str

    def to_dict(self) -> dict:
        return {
            "fields": self.fields,
            "confidence": self.confidence,
            "notes": self.notes,
            "raw_model_text": self.raw_model_text,
        }


class OcrServiceError(RuntimeError):
    pass


def extract_from_image(
    file_bytes: bytes,
    media_type: str,
    hint: OcrHint,
    *,
    client=None,
    model: Optional[str] = None,
) -> OcrResult:
    """
    Extract structured fields from a bill/invoice image or PDF.

    `client` is injectable for testing — in prod we build an Anthropic client
    from ANTHROPIC_API_KEY.
    """
    if media_type not in SUPPORTED_MEDIA:
        raise OcrServiceError(f"unsupported media type: {media_type}")
    if hint not in _HINT_INSTRUCTIONS:
        raise OcrServiceError(f"unknown hint: {hint}")

    if client is None:
        client = _build_client()

    model = model or os.getenv("ANTHROPIC_OCR_MODEL", "claude-sonnet-4-6")

    instructions = _HINT_INSTRUCTIONS[hint]
    system = (
        "You are an expert at reading scanned Indian utility bills and textile "
        "supplier invoices, including bilingual (Tamil + English) documents.\n"
        "Return ONLY a single JSON object matching the requested schema. No "
        "prose, no markdown, no code fences. Numbers must be numbers (not "
        "strings). Dates must be ISO YYYY-MM-DD. Unknown fields must be null.\n"
        "Include a top-level 'confidence' field between 0 and 1 reflecting how "
        "confident you are in the overall extraction, and a top-level 'notes' "
        "string for anything the human operator should double-check "
        "(e.g. 'image is blurry around the units field').\n"
    )
    user_text = (
        f"{instructions}\n\n"
        "Return a JSON object of the form:\n"
        '  { "fields": { ... per-hint fields ... }, '
        '    "confidence": <0..1>, "notes": "<string>" }'
    )

    image_block = _build_image_block(file_bytes, media_type)

    logger.info("ocr.extract start hint=%s media=%s bytes=%d", hint, media_type, len(file_bytes))
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[
            {
                "role": "user",
                "content": [
                    image_block,
                    {"type": "text", "text": user_text},
                ],
            }
        ],
    )

    text = _concat_text(response)
    parsed = _parse_json_strict(text)

    return OcrResult(
        fields=parsed.get("fields", {}),
        confidence=float(parsed.get("confidence", 0.0) or 0.0),
        notes=str(parsed.get("notes") or ""),
        raw_model_text=text,
    )


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


def _build_client():
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as exc:
        raise OcrServiceError(
            "anthropic SDK not installed — add `anthropic` to requirements.txt"
        ) from exc
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise OcrServiceError("ANTHROPIC_API_KEY is not configured")
    return Anthropic(api_key=api_key)


def _build_image_block(file_bytes: bytes, media_type: str) -> dict:
    b64 = base64.b64encode(file_bytes).decode("ascii")
    if media_type == "application/pdf":
        # Anthropic supports native PDF inputs under the 'document' block.
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": b64},
    }


def _concat_text(response) -> str:
    # The Anthropic SDK returns response.content as a list of content blocks.
    out: list[str] = []
    for block in getattr(response, "content", []) or []:
        # block can be an object with `.type` and `.text`, or a dict.
        t = getattr(block, "type", None) or (isinstance(block, dict) and block.get("type"))
        if t == "text":
            text = getattr(block, "text", None) or (isinstance(block, dict) and block.get("text"))
            if text:
                out.append(text)
    return "\n".join(out).strip()


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _parse_json_strict(text: str) -> dict:
    """
    The system prompt asks for raw JSON, but models occasionally wrap it in
    markdown fences. Strip fences then try once; if that fails, try to locate
    the outermost JSON object in the text.
    """
    if not text:
        raise OcrServiceError("empty response from model")

    candidate = text.strip()
    m = _FENCE_RE.search(candidate)
    if m:
        candidate = m.group(1).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Fallback: outermost {...}
    first = candidate.find("{")
    last = candidate.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            return json.loads(candidate[first : last + 1])
        except json.JSONDecodeError as exc:
            raise OcrServiceError(f"model returned non-JSON: {exc}") from exc

    raise OcrServiceError("could not locate a JSON object in the model response")
