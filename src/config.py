from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_DIR = PROJECT_ROOT / "logs"
DATABASE_PATH = DATA_DIR / "tesla_jobs.db"
WORKBOOK_PATH = OUTPUT_DIR / "Tesla_New_Jobs.xlsx"
LOG_PATH = LOG_DIR / "tesla_job_tracker.log"

# Verified from Tesla's live careers web application.  The endpoint returns a
# single state document containing the complete global listing catalogue.
CAREERS_STATE_URL = "https://www.tesla.com/cua-api/apps/careers/state"
CAREERS_JOB_URL = "https://www.tesla.com/careers/search/job/tjt-{job_id}"
REQUEST_TIMEOUT_SECONDS = 45
REQUEST_RETRIES = 3
REQUEST_BACKOFF_SECONDS = 2
