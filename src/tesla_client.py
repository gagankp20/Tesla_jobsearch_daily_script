"""HTTP client for Tesla's public careers state endpoint."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from .config import CAREERS_STATE_URL, REQUEST_BACKOFF_SECONDS, REQUEST_RETRIES, REQUEST_TIMEOUT_SECONDS
from .parser import Job, TeslaSchemaError, parse_jobs

LOGGER = logging.getLogger(__name__)


class TeslaFetchError(RuntimeError):
    pass


class TeslaClient:
    def __init__(self, session: requests.Session | None = None, endpoint: str = CAREERS_STATE_URL) -> None:
        self.session = session or requests.Session()
        self.endpoint = endpoint

    def fetch_payload(self) -> dict[str, Any]:
        headers = {"Accept": "application/json", "User-Agent": "TeslaJobTracker/1.0 (personal local tracker)"}
        last_error: Exception | None = None
        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                response = self.session.get(self.endpoint, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
                if response.status_code in {401, 403, 429}:
                    raise TeslaFetchError(
                        f"Tesla blocked or rate-limited this request (HTTP {response.status_code}). "
                        "The tracker will not bypass access controls; try again later in a normal network/browser session."
                    )
                response.raise_for_status()
                try:
                    data = response.json()
                except ValueError as exc:
                    snippet = response.text[:160].replace("\n", " ")
                    raise TeslaFetchError(f"Tesla endpoint did not return JSON: {snippet!r}") from exc
                if not isinstance(data, dict):
                    raise TeslaFetchError("Tesla endpoint returned JSON but not a JSON object.")
                return data
            except (requests.RequestException, TeslaFetchError) as exc:
                last_error = exc
                LOGGER.warning("Tesla request attempt %s/%s failed: %s", attempt, REQUEST_RETRIES, exc)
                if isinstance(exc, TeslaFetchError) and "blocked or rate-limited" in str(exc):
                    break
                if attempt < REQUEST_RETRIES:
                    time.sleep(REQUEST_BACKOFF_SECONDS * attempt)
        raise TeslaFetchError(f"Unable to fetch Tesla careers state from {self.endpoint}: {last_error}")

    def fetch_jobs(self) -> list[Job]:
        try:
            return parse_jobs(self.fetch_payload())
        except TeslaSchemaError as exc:
            raise TeslaFetchError(f"Tesla response format is incompatible with this tracker: {exc}") from exc
