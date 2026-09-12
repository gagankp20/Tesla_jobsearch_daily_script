"""Daily Tesla US full-time job change tracker."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from .config import CAREERS_STATE_URL, DATA_DIR, LOG_DIR, OUTPUT_DIR, DATABASE_PATH, LOG_PATH, WORKBOOK_PATH
from .database import JobDatabase
from .excel_exporter import export_workbook
from .parser import TeslaSchemaError, parse_jobs
from .tesla_client import TeslaClient, TeslaFetchError


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()])


def main() -> int:
    parser = argparse.ArgumentParser(description="Track new Tesla US full-time jobs.")
    parser.add_argument("--baseline", action="store_true", help="Replace the database with the current inventory; do not report new jobs.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report changes without writing database or Excel files.")
    parser.add_argument("--force", action="store_true", help="Allow a normal scan on an empty database to report current jobs as new (testing only).")
    parser.add_argument("--import-state", metavar="FILE", help="Process a careers-state JSON file manually saved from an authorized browser session.")
    parser.add_argument("--baseline-date", metavar="YYYY-MM-DD", help="Discovery date to assign when creating or replacing a baseline.")
    parser.add_argument("--set-baseline-date", metavar="YYYY-MM-DD", help="Update the discovery date of existing baseline jobs without changing later discoveries.")
    args = parser.parse_args()
    configure_logging()
    logger = logging.getLogger(__name__)
    DATA_DIR.mkdir(exist_ok=True); OUTPUT_DIR.mkdir(exist_ok=True)
    db = JobDatabase(DATABASE_PATH); db.initialize()
    try:
        baseline_date = date.fromisoformat(args.baseline_date).isoformat() if args.baseline_date else None
        set_baseline_date = date.fromisoformat(args.set_baseline_date).isoformat() if args.set_baseline_date else None
    except ValueError:
        parser.error("baseline dates must use YYYY-MM-DD (for example, 2026-08-01)")
    if set_baseline_date:
        if args.baseline_date or args.baseline or args.force or args.import_state:
            parser.error("--set-baseline-date is a standalone command")
        changed = db.set_baseline_discovery_date(set_baseline_date)
        export_workbook(WORKBOOK_PATH, db.new_job_history(), db.current_jobs())
        print(f"Updated the discovery date for {changed:,} baseline Tesla jobs to {set_baseline_date}.")
        return 0
    source = CAREERS_STATE_URL if not args.import_state else f"file:{args.import_state}"
    logger.info("Starting Tesla job scan; source=%s", source)
    scan_id = None if args.dry_run else db.start_scan(source)
    try:
        if args.import_state:
            try:
                with open(args.import_state, encoding="utf-8-sig") as state_file:
                    jobs = parse_jobs(json.load(state_file))
            except FileNotFoundError as exc:
                raise TeslaFetchError(f"Imported state file was not found: {args.import_state}") from exc
            except json.JSONDecodeError as exc:
                raise TeslaFetchError(f"Imported state file is not valid JSON: {exc}") from exc
            except TeslaSchemaError as exc:
                raise TeslaFetchError(f"Imported state is not a compatible Tesla careers-state document: {exc}") from exc
        else:
            jobs = TeslaClient().fetch_jobs()
        if not jobs:
            raise TeslaFetchError("Tesla returned a valid state but no US full-time jobs. Refusing to mark all saved jobs inactive.")
        ids = [job.job_id for job in jobs]
        if len(ids) != len(set(ids)):
            raise TeslaFetchError("Duplicate Req IDs found after parsing; no data was written.")
        logger.info("Fetched %d unique Tesla US full-time jobs", len(jobs))
        existing_baseline = db.has_jobs()
        if args.dry_run:
            existing = sum(1 for job in jobs if job.job_id in {r["job_id"] for r in db.current_jobs()})
            logger.info("Dry run: %d would be new; %d already exist", len(jobs) - existing, existing)
            print(f"Dry run: {len(jobs) - existing} new, {existing} existing. No files changed.")
            return 0
        if args.baseline or (not existing_baseline and not args.force):
            db.replace_baseline(jobs, baseline_date)
            export_workbook(WORKBOOK_PATH, [], db.current_jobs())
            db.finish_scan(scan_id, "success", len(jobs), 0, 0)
            print(f"Initial baseline created: {len(jobs):,} Tesla jobs recorded. No jobs marked as new.")
            return 0
        new_rows, existing = db.record_jobs(jobs)
        export_workbook(WORKBOOK_PATH, db.new_job_history(), db.current_jobs())
        db.finish_scan(scan_id, "success", len(jobs), len(new_rows), existing)
        logger.info("Completed scan: new=%d existing=%d", len(new_rows), existing)
        print(f"Scan complete: {len(new_rows)} new Tesla jobs; {existing} existing jobs.")
        return 0
    except Exception as exc:
        logger.exception("Tesla job scan failed: %s", exc)
        if scan_id is not None:
            db.finish_scan(scan_id, "failed", error=str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
