"""
Daily Merkle anchoring.

Once a day we:
  1. Gather every Report signed during the previous UTC day (i.e. reports
     whose payload_hash is set and have no merkle_anchor_id yet).
  2. Build a Merkle tree over those payload_hashes.
  3. Persist the root + per-leaf inclusion proofs in a MerkleAnchor row.
  4. Link each Report to the anchor so the public verify endpoint can serve
     the proof.
  5. (Optional, best-effort) Submit the root to OpenTimestamps so it becomes
     Bitcoin-anchored. OTS upgrades happen asynchronously (minutes to hours);
     a separate `upgrade_pending_anchors()` call picks the upgraded proof
     back up and stores it.

The Merkle design is intentionally vanilla: sha256 pair hashing, last-leaf
duplication to pad odd levels. The proof format is a list of
"<sibling_hex>:L" / "<sibling_hex>:R" strings — easy to verify in any
language without a custom library.

Verifying an inclusion proof, given a leaf hash, the proof list, and the
expected root:
    node = leaf
    for step in proof:
        sibling_hex, side = step.split(":")
        sibling = bytes.fromhex(sibling_hex)
        if side == "L":
            node = sha256(sibling + node)
        else:
            node = sha256(node + sibling)
    assert node.hex() == root_hex
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ..models import MerkleAnchor, Report

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure Merkle — easy to unit-test
# ---------------------------------------------------------------------------


def _h(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def build_tree(leaf_hex_hashes: list[str]) -> tuple[str, dict[str, list[str]]]:
    """
    Return (merkle_root_hex, inclusion_proofs) for the given leaves.

    inclusion_proofs is keyed by leaf hash hex; each value is a list of
    "sibling_hex:side" steps to combine with to reach the root.
    """
    if not leaf_hex_hashes:
        raise ValueError("cannot build a Merkle tree with zero leaves")

    leaves = [bytes.fromhex(h) for h in leaf_hex_hashes]

    # We need to track, for each leaf, the sequence of siblings. We do it the
    # straightforward way: iterate levels, remembering sibling-of-each-index.
    level = leaves
    # proofs[i] is the list of sibling:side pairs for leaf i so far
    proofs: list[list[str]] = [[] for _ in leaves]
    # index_map maps current-level index to the original leaf indices under
    # that position — so we know whose proof to extend when we pair up.
    index_map: list[list[int]] = [[i] for i in range(len(leaves))]

    while len(level) > 1:
        next_level: list[bytes] = []
        next_index_map: list[list[int]] = []
        # Duplicate last to pair odd counts.
        if len(level) % 2 == 1:
            level = level + [level[-1]]
            index_map = index_map + [index_map[-1]]
        for i in range(0, len(level), 2):
            left, right = level[i], level[i + 1]
            left_idxs = index_map[i]
            right_idxs = index_map[i + 1]
            # Record sibling for every leaf under left (sibling = right, R side).
            for idx in left_idxs:
                proofs[idx].append(f"{right.hex()}:R")
            # ...and for every leaf under right (sibling = left, L side).
            # If right is the duplicated last-leaf pad, don't double-record for
            # already-covered indices.
            for idx in right_idxs:
                if idx in left_idxs:
                    continue
                proofs[idx].append(f"{left.hex()}:L")
            next_level.append(_h(left + right))
            next_index_map.append(sorted(set(left_idxs + right_idxs)))
        level = next_level
        index_map = next_index_map

    root_hex = level[0].hex()
    inclusion = {h: p for h, p in zip(leaf_hex_hashes, proofs)}
    return root_hex, inclusion


def verify_inclusion(leaf_hex: str, proof: Iterable[str], root_hex: str) -> bool:
    node = bytes.fromhex(leaf_hex)
    for step in proof:
        sibling_hex, side = step.split(":")
        sibling = bytes.fromhex(sibling_hex)
        if side == "L":
            node = _h(sibling + node)
        elif side == "R":
            node = _h(node + sibling)
        else:
            return False
    return node.hex() == root_hex


# ---------------------------------------------------------------------------
# DB integration: anchor yesterday's reports
# ---------------------------------------------------------------------------


def anchor_reports_for_day(db: Session, *, day_utc: Optional[datetime] = None) -> Optional[MerkleAnchor]:
    """
    Build an anchor covering all reports created on the given UTC day
    (defaults to yesterday) that don't already belong to an anchor.

    Idempotent: if an anchor already exists for that day, skips unclaimed
    reports rather than building a competing anchor. (We could also amend the
    existing anchor, but keeping anchors immutable is simpler to reason about.)
    """
    if day_utc is None:
        now = datetime.now(timezone.utc)
        day_utc = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=1)
    else:
        day_utc = day_utc.astimezone(timezone.utc)
        day_utc = datetime(day_utc.year, day_utc.month, day_utc.day, tzinfo=timezone.utc)

    day_end = day_utc + timedelta(days=1)

    existing = (
        db.query(MerkleAnchor)
        .filter(MerkleAnchor.anchor_date == day_utc)
        .first()
    )
    if existing:
        logger.info("merkle_anchor already exists for %s (id=%s)", day_utc.date(), existing.id)
        return existing

    reports = (
        db.query(Report)
        .filter(
            Report.payload_hash.isnot(None),
            Report.merkle_anchor_id.is_(None),
            Report.created_at >= day_utc,
            Report.created_at < day_end,
        )
        .order_by(Report.id.asc())
        .all()
    )
    if not reports:
        logger.info("no reports to anchor for %s", day_utc.date())
        return None

    leaves = [r.payload_hash for r in reports]
    root, proofs = build_tree(leaves)

    anchor = MerkleAnchor(
        anchor_date=day_utc,
        merkle_root_hex=root,
        leaf_count=len(leaves),
        inclusion_proofs=proofs,
    )
    db.add(anchor)
    db.flush()

    for r in reports:
        r.merkle_anchor_id = anchor.id

    # Best-effort OTS submission. If the ots-client binary isn't installed
    # or the network is down, we still commit the anchor — the proof can be
    # attached later via `upgrade_pending_anchors`.
    try:
        proof_hex = submit_to_opentimestamps(bytes.fromhex(root))
        if proof_hex:
            anchor.ots_proof_hex = proof_hex
            anchor.ots_submitted_at = datetime.now(timezone.utc)
    except Exception:
        logger.exception("OTS submission failed for anchor %s", anchor.id)

    db.commit()
    logger.info(
        "merkle anchor day=%s root=%s leaves=%d",
        day_utc.date(),
        root[:16],
        len(leaves),
    )
    return anchor


def submit_to_opentimestamps(root_bytes: bytes) -> Optional[str]:
    """
    Submit the Merkle root to OpenTimestamps and return the initial proof as
    hex, or None if the `ots` CLI isn't available.

    We shell out to the `ots` command rather than depending on the
    opentimestamps-client Python library (which is heavy and has its own
    transitive issues). If you don't want a system dependency, swap this for
    the library — the rest of the anchor flow doesn't care.
    """
    import tempfile
    import os as _os

    try:
        subprocess.run(["ots", "--version"], capture_output=True, check=False, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.info("ots CLI not available; skipping OpenTimestamps submission")
        return None

    with tempfile.TemporaryDirectory() as td:
        data_path = _os.path.join(td, "root.bin")
        with open(data_path, "wb") as f:
            f.write(root_bytes)
        ots_path = data_path + ".ots"
        proc = subprocess.run(
            ["ots", "stamp", data_path],
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            logger.warning("ots stamp failed: %s", proc.stderr.decode(errors="ignore"))
            return None
        if not _os.path.exists(ots_path):
            logger.warning("ots stamp did not produce %s", ots_path)
            return None
        with open(ots_path, "rb") as f:
            return f.read().hex()


def upgrade_pending_anchors(db: Session) -> int:
    """
    For every anchor whose OTS proof isn't yet Bitcoin-attested, re-run
    `ots upgrade`. Returns the number of anchors upgraded.

    Runs on a slower schedule than `anchor_reports_for_day` (e.g. hourly) —
    OTS attestations take a few hours typically.
    """
    import tempfile
    import os as _os

    anchors = (
        db.query(MerkleAnchor)
        .filter(
            MerkleAnchor.ots_proof_hex.isnot(None),
            MerkleAnchor.ots_upgraded_at.is_(None),
        )
        .all()
    )
    upgraded = 0
    for a in anchors:
        with tempfile.TemporaryDirectory() as td:
            data = bytes.fromhex(a.merkle_root_hex)
            data_path = _os.path.join(td, "root.bin")
            ots_path = data_path + ".ots"
            with open(data_path, "wb") as f:
                f.write(data)
            with open(ots_path, "wb") as f:
                f.write(bytes.fromhex(a.ots_proof_hex))
            proc = subprocess.run(
                ["ots", "upgrade", ots_path],
                capture_output=True,
                timeout=60,
            )
            if proc.returncode != 0:
                logger.info("ots upgrade pending for anchor=%s", a.id)
                continue
            with open(ots_path, "rb") as f:
                a.ots_proof_hex = f.read().hex()
            a.ots_upgraded_at = datetime.now(timezone.utc)
            upgraded += 1
    if upgraded:
        db.commit()
    return upgraded
