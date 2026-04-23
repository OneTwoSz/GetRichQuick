"""
Append-only audit logger with SHA-256 hash chaining.

Every new row's `payload_hash` is:
    sha256( canonical_json({
        "factory_id": ...,
        "user_id": ...,
        "action": ...,
        "entity_type": ...,
        "entity_id": ...,
        "old_value": ...,
        "new_value": ...,
        "prev_hash": "<previous row's payload_hash or null>",
    }) )

Effect: flipping any cell in any row breaks the chain from that point on.
Combined with the daily Merkle-root-to-OpenTimestamps anchor (see
services/merkle_service.py), tampering with the DB after the anchor point
becomes detectable even by a buyer who wasn't there at write time.

Notes:
  - prev_hash is per-factory (each factory has an independent chain).
  - Old rows without hashes continue to work; the first new row after the
    upgrade treats prev_hash as NULL.
  - model_to_dict coerces datetime/enum to primitives so canonical_json
    can serialize safely.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..models import AuditLog
from ..utils.hashing import canonical_json, sha256_hex


class AuditLogger:
    """Service for logging all data changes for audit trail."""

    @staticmethod
    def _latest_hash(db: Session, factory_id: int) -> Optional[str]:
        """Return the most recent payload_hash for the factory, or None."""
        row = (
            db.query(AuditLog)
            .filter(
                AuditLog.factory_id == factory_id,
                AuditLog.payload_hash.isnot(None),
            )
            .order_by(AuditLog.id.desc())
            .first()
        )
        return row.payload_hash if row else None

    @staticmethod
    def log_action(
        db: Session,
        factory_id: int,
        user_id: int,
        action: str,  # CREATE, UPDATE, DELETE
        entity_type: str,  # production_record, chemical, etc.
        entity_id: int,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Append a row to the audit trail, chained to the previous one."""
        prev_hash = AuditLogger._latest_hash(db, factory_id)

        content = {
            "factory_id": factory_id,
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_value": old_value,
            "new_value": new_value,
            "prev_hash": prev_hash,
        }
        payload_hash = sha256_hex(canonical_json(content))

        audit_log = AuditLog(
            factory_id=factory_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            prev_hash=prev_hash,
            payload_hash=payload_hash,
        )

        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log

    @staticmethod
    def model_to_dict(model_instance) -> Dict[str, Any]:
        """
        Convert SQLAlchemy model to dict for audit logging.

        Datetimes/Enums are left as-is here because canonical_json's default
        serializer handles them. Callers should not strip types.
        """
        return {
            c.name: getattr(model_instance, c.name)
            for c in model_instance.__table__.columns
        }

    @staticmethod
    def verify_chain(db: Session, factory_id: int) -> Dict[str, Any]:
        """
        Walk the chain for a factory and report the first break.

        Returns:
            {
              "total": <int>,
              "verified": <int>,          # rows with valid hashes
              "broken_at_id": <int|None>, # first row whose hash doesn't match
              "ok": <bool>,
            }

        Pre-upgrade rows (payload_hash == None) are counted as "total" but
        not "verified" — they can't be checked, only preserved.
        """
        rows = (
            db.query(AuditLog)
            .filter(AuditLog.factory_id == factory_id)
            .order_by(AuditLog.id.asc())
            .all()
        )
        prev_hash: Optional[str] = None
        verified = 0
        broken_at: Optional[int] = None
        for row in rows:
            if row.payload_hash is None:
                # Legacy pre-chaining row — skip, don't update prev_hash.
                continue
            content = {
                "factory_id": row.factory_id,
                "user_id": row.user_id,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "old_value": row.old_value,
                "new_value": row.new_value,
                "prev_hash": row.prev_hash,
            }
            expected = sha256_hex(canonical_json(content))
            if expected != row.payload_hash:
                broken_at = row.id
                break
            if row.prev_hash != prev_hash and prev_hash is not None:
                # The link doesn't connect to the previous verified row.
                broken_at = row.id
                break
            prev_hash = row.payload_hash
            verified += 1
        return {
            "total": len(rows),
            "verified": verified,
            "broken_at_id": broken_at,
            "ok": broken_at is None,
        }
