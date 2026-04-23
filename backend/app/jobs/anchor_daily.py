"""
Daily Merkle anchor job.

Usage:
    python -m app.jobs.anchor_daily              # anchor yesterday
    python -m app.jobs.anchor_daily 2026-04-22   # anchor a specific day
    python -m app.jobs.anchor_daily upgrade      # run OTS upgrade pass

In prod this is triggered by cron (or a Kubernetes CronJob) once per day a
bit after midnight UTC. The OTS-upgrade pass should run hourly.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from ..database import SessionLocal
from ..services.merkle_service import anchor_reports_for_day, upgrade_pending_anchors

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("anchor_daily")


def _parse_day(arg: str) -> datetime:
    try:
        return datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        logger.error("invalid date %r — expected YYYY-MM-DD", arg)
        sys.exit(2)


def main(argv: list[str]) -> int:
    db = SessionLocal()
    try:
        if len(argv) >= 2 and argv[1] == "upgrade":
            n = upgrade_pending_anchors(db)
            logger.info("upgraded %d anchor(s)", n)
            return 0

        day = _parse_day(argv[1]) if len(argv) >= 2 else None
        anchor = anchor_reports_for_day(db, day_utc=day)
        if anchor:
            logger.info(
                "anchor id=%s root=%s leaves=%d ots_submitted=%s",
                anchor.id,
                anchor.merkle_root_hex[:16],
                anchor.leaf_count,
                bool(anchor.ots_submitted_at),
            )
        else:
            logger.info("nothing to anchor")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
