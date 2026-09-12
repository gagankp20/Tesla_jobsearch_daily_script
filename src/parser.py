"""Parse Tesla's compact careers-state JSON into normalized jobs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .config import CAREERS_JOB_URL


class TeslaSchemaError(RuntimeError):
    """The careers state response did not have Tesla's expected structure."""


@dataclass(frozen=True)
class Job:
    job_id: str
    title: str
    location: str
    category: str
    employment_type: str
    url: str
    posted_at: str | None = None


US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "district of columbia", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky",
    "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire",
    "new jersey", "new mexico", "new york", "north carolina", "north dakota",
    "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming", "puerto rico",
}


def _lookup_value(lookup: dict[str, Any], group: str, key: Any) -> str:
    values = lookup.get(group, {})
    value = values.get(str(key), values.get(key, "")) if isinstance(values, dict) else ""
    if isinstance(value, dict):
        return str(value.get("label") or value.get("name") or value.get("title") or "")
    return str(value or "")


def _value(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        if item.get(name) is not None:
            return item[name]
    return None


def _is_full_time(value: str) -> bool:
    return value.strip().casefold().replace("-", " ") in {"full time", "fulltime"}


def _is_us_job(item: dict[str, Any], location: str, location_key: Any) -> bool:
    """Match Tesla's US site filter without guessing from arbitrary city names."""
    values = " ".join(str(v) for v in (location, location_key, item.get("country"), item.get("countryCode"), item.get("site")) if v)
    lowered = values.casefold()
    if any(token in lowered for token in ("united states", "usa", "us-", "us_", "country:us")):
        return True
    if location.strip().casefold() == "remote":
        return True  # Tesla includes Remote in its US site filter.
    parts = [part.strip().casefold() for part in location.split(",")]
    return bool(parts and parts[-1] in US_STATE_NAMES)


def parse_jobs(payload: dict[str, Any]) -> list[Job]:
    """Return all US full-time jobs, with robust errors for a changed endpoint."""
    if not isinstance(payload, dict):
        raise TeslaSchemaError("Tesla careers state was not a JSON object.")
    listings = payload.get("listings")
    lookup = payload.get("lookup")
    if not isinstance(listings, list) or not isinstance(lookup, dict):
        raise TeslaSchemaError(
            "Tesla careers endpoint schema changed: expected JSON keys 'listings' (array) "
            "and 'lookup' (object)."
        )

    jobs: list[Job] = []
    seen: set[str] = set()
    for item in listings:
        if not isinstance(item, dict):
            continue
        raw_id = _value(item, "id", "job_id", "jobId")
        if raw_id is None:
            continue
        job_id = str(raw_id).strip()
        title = str(_value(item, "t", "title", "name") or "").strip()
        location_key = _value(item, "l", "location", "location_id")
        department_key = _value(item, "dp", "department", "category")
        type_key = _value(item, "y", "type", "employment_type", "employmentType")
        location = _lookup_value(lookup, "locations", location_key) or str(location_key or "")
        category = _lookup_value(lookup, "departments", department_key) or str(department_key or "")
        employment_type = _lookup_value(lookup, "types", type_key) or str(type_key or "")
        if not job_id or not title:
            continue
        if not _is_full_time(employment_type) or not _is_us_job(item, location, location_key):
            continue
        if job_id in seen:
            raise TeslaSchemaError(f"Tesla response contained duplicate Req ID {job_id!r}.")
        seen.add(job_id)
        # The verified state feed has no posting/created field.  Never infer one.
        jobs.append(Job(job_id, title, location, category, employment_type,
                        CAREERS_JOB_URL.format(job_id=job_id), None))
    return jobs
