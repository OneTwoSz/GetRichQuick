"""
Canonical JSON + SHA-256 helpers.

Any feature that computes a hash over structured data (report payload, audit
log entry, Merkle leaf) MUST use `canonical_json()` so the hash is
deterministic across:
  - Python versions
  - dict ordering
  - whitespace differences

Conventions:
  - keys sorted lexicographically
  - separators (",", ":") — no extra whitespace
  - ensure_ascii=False so Tamil chemical names round-trip cleanly
  - datetimes are serialized as ISO-8601 UTC with a trailing 'Z'
  - sets and tuples are not supported — convert to lists before hashing
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any


def _default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        # Normalize to UTC with Z suffix. Naive datetimes are assumed UTC.
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        else:
            obj = obj.astimezone(timezone.utc)
        return obj.isoformat().replace("+00:00", "Z")
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        # Use str() rather than float() to avoid precision loss.
        return str(obj)
    if hasattr(obj, "value"):  # SQLAlchemy Enum instances
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON bytes for hashing."""
    return json.dumps(
        obj,
        default=_default,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_json(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))
