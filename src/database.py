"""SQLite persistence and change detection."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

from .parser import Job


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def discovery_timestamp() -> str:
    """Return the local date and time at which a listing was discovered.

    Stored as an ISO timestamp (for example ``2026-09-11T14:23:05``) so the
    Excel export can show both a discovery date and a discovery time, which
    matters when the scan is run more than once in a single day.
    """
    return datetime.now().replace(microsecond=0).isoformat()


class JobDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def initialize(self) -> None:
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, title TEXT NOT NULL, location TEXT,
                    category TEXT, employment_type TEXT, url TEXT NOT NULL,
                    posted_at TEXT, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1, was_new INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
                    completed_at TEXT, status TEXT NOT NULL, endpoint TEXT NOT NULL,
                    jobs_fetched INTEGER DEFAULT 0, new_jobs INTEGER DEFAULT 0,
                    existing_jobs INTEGER DEFAULT 0, error_message TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at DESC);
            """)
            columns = {row[1] for row in con.execute("PRAGMA table_info(jobs)")}
            if "was_new" not in columns:
                con.execute("ALTER TABLE jobs ADD COLUMN was_new INTEGER NOT NULL DEFAULT 0")

    def has_jobs(self) -> bool:
        with self.connect() as con:
            return con.execute("SELECT EXISTS(SELECT 1 FROM jobs)").fetchone()[0] == 1

    def start_scan(self, endpoint: str) -> int:
        with self.connect() as con:
            cur = con.execute("INSERT INTO scans (started_at, status, endpoint) VALUES (?, 'running', ?)", (utc_now(), endpoint))
            return int(cur.lastrowid)

    def finish_scan(self, scan_id: int, status: str, fetched: int = 0, new: int = 0, existing: int = 0, error: str | None = None) -> None:
        with self.connect() as con:
            con.execute("""UPDATE scans SET completed_at=?, status=?, jobs_fetched=?, new_jobs=?, existing_jobs=?, error_message=?
                           WHERE scan_id=?""", (utc_now(), status, fetched, new, existing, error, scan_id))

    def replace_baseline(self, jobs: Sequence[Job], first_seen_date: str | None = None) -> None:
        """Replace the initial inventory, assigning it one discovery date."""
        now = discovery_timestamp() if first_seen_date is None else first_seen_date
        with self.connect() as con:
            con.execute("DELETE FROM jobs")
            con.executemany("""INSERT INTO jobs(job_id,title,location,category,employment_type,url,posted_at,first_seen_at,last_seen_at,is_active,was_new)
                VALUES(?,?,?,?,?,?,?,?,?,1,0)""", [(j.job_id,j.title,j.location,j.category,j.employment_type,j.url,j.posted_at,now,now) for j in jobs])

    def set_baseline_discovery_date(self, date: str) -> int:
        """Restamp initial-baseline listings without changing later discoveries."""
        with self.connect() as con:
            cur = con.execute("UPDATE jobs SET first_seen_at=? WHERE was_new=0", (date,))
            return cur.rowcount

    def record_jobs(self, jobs: Sequence[Job]) -> tuple[list[sqlite3.Row], int]:
        now = discovery_timestamp()
        ids = [j.job_id for j in jobs]
        with self.connect() as con:
            if ids:
                placeholders = ",".join("?" for _ in ids)
                old_ids = {row[0] for row in con.execute(f"SELECT job_id FROM jobs WHERE job_id IN ({placeholders})", ids)}
            else:
                old_ids = set()
            new_jobs = [j for j in jobs if j.job_id not in old_ids]
            con.execute("UPDATE jobs SET is_active=0 WHERE is_active=1")
            for job in jobs:
                con.execute("""INSERT INTO jobs(job_id,title,location,category,employment_type,url,posted_at,first_seen_at,last_seen_at,is_active,was_new)
                    VALUES(?,?,?,?,?,?,?,?,?,1,?)
                    ON CONFLICT(job_id) DO UPDATE SET title=excluded.title,location=excluded.location,category=excluded.category,
                    employment_type=excluded.employment_type,url=excluded.url,posted_at=COALESCE(excluded.posted_at,jobs.posted_at),
                    last_seen_at=excluded.last_seen_at,is_active=1""",
                    (job.job_id,job.title,job.location,job.category,job.employment_type,job.url,job.posted_at,now,now, 0 if job.job_id in old_ids else 1))
            if new_jobs:
                placeholders = ",".join("?" for _ in new_jobs)
                rows = list(con.execute(
                    f"SELECT * FROM jobs WHERE job_id IN ({placeholders}) ORDER BY first_seen_at DESC, job_id DESC",
                    [j.job_id for j in new_jobs],
                ))
            else:
                rows = []
            return rows, len(old_ids)

    def current_jobs(self) -> list[sqlite3.Row]:
        with self.connect() as con:
            return list(con.execute("SELECT * FROM jobs WHERE is_active=1 ORDER BY COALESCE(posted_at, first_seen_at) DESC, job_id DESC"))

    def new_job_history(self) -> list[sqlite3.Row]:
        with self.connect() as con:
            return list(con.execute("SELECT * FROM jobs WHERE was_new=1 ORDER BY first_seen_at DESC, job_id DESC"))
