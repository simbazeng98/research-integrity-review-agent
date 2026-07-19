from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

# Default cache directory under the project
DEFAULT_CACHE_DIR = Path(".cache/crossref")

# User-Agent for Crossref polite API usage
USER_AGENT = "ResearchIntegrityEvidenceReviewAgent/0.4 (mailto:optional@example.com)"


class CrossrefClientError(Exception):
    """Base exception for Crossref client errors."""
    pass


class CrossrefNotFoundError(CrossrefClientError):
    """Raised when the DOI is not found (HTTP 404)."""
    pass


class CrossrefRateLimitError(CrossrefClientError):
    """Raised when the client is rate limited (HTTP 429)."""
    pass


# Local mock fixtures for offline execution and testing
MOCK_FIXTURES: dict[str, dict[str, Any]] = {
    "10.0000/toy-retracted": {
        "status": "ok",
        "message": {
            "DOI": "10.0000/toy-retracted",
            "title": ["Mock Retracted Article"],
            "publisher": "Mock Publisher Ltd",
            "updated-by": [
                {
                    "type": "retraction",
                    "DOI": "10.0000/toy-retracted-notice",
                    "label": "Retraction notice",
                    "updated": {"date-parts": [[2025, 6, 1]]}
                }
            ]
        }
    },
    "10.0000/toy-corrected": {
        "status": "ok",
        "message": {
            "DOI": "10.0000/toy-corrected",
            "title": ["Mock Corrected Article"],
            "publisher": "Mock Publisher Ltd",
            "updated-by": [
                {
                    "type": "correction",
                    "DOI": "10.0000/toy-corrected-notice",
                    "label": "Correction notice",
                    "updated": {"date-parts": [[2024, 5, 1]]}
                }
            ]
        }
    },
    "10.0000/toy-eoc": {
        "status": "ok",
        "message": {
            "DOI": "10.0000/toy-eoc",
            "title": ["Mock EOC Article"],
            "publisher": "Mock Publisher Ltd",
            "updated-by": [
                {
                    "type": "expression_of_concern",
                    "DOI": "10.0000/toy-eoc-notice",
                    "label": "Expression of Concern notice",
                    "updated": {"date-parts": [[2026, 1, 15]]}
                }
            ]
        }
    },
    "10.0000/toy-no-update": {
        "status": "ok",
        "message": {
            "DOI": "10.0000/toy-no-update",
            "title": ["Mock Stable Article"],
            "publisher": "Mock Publisher Ltd",
            "updated-by": []
        }
    },
    "10.0000/toy-rule-runtime": {
        "status": "ok",
        "message": {
            "DOI": "10.0000/toy-rule-runtime",
            "title": ["Mock Rule Runtime Article"],
            "publisher": "Mock Publisher Ltd",
            "updated-by": [
                {
                    "type": "expression_of_concern",
                    "DOI": "10.0000/toy-rule-runtime-notice",
                    "label": "Mock EOC",
                    "updated": {"date-parts": [[2026, 7, 4]]}
                }
            ]
        }
    },
    "10.0000/toy-doi": {
        "status": "ok",
        "message": {
            "DOI": "10.0000/toy-doi",
            "title": ["Mock General Toy DOI"],
            "publisher": "Mock Publisher Ltd",
            "updated-by": []
        }
    },
    "10.0000/toy-withdrawal": {
        "status": "ok",
        "message": {
            "DOI": "10.0000/toy-withdrawal",
            "title": ["Mock Withdrawn Article"],
            "publisher": "Mock Publisher Ltd",
            "updated-by": [
                {
                    "type": "withdrawal",
                    "DOI": "10.0000/toy-withdrawal-notice",
                    "label": "Withdrawal notice",
                    "updated": {"date-parts": [[2025, 8, 15]]}
                }
            ]
        }
    },
    "10.0000/toy-update-notice": {
        "status": "ok",
        "message": {
            "DOI": "10.0000/toy-update-notice",
            "title": ["Mock Update Notice Article"],
            "publisher": "Mock Publisher Ltd",
            "updated-by": [
                {
                    "type": "update",
                    "DOI": "10.0000/toy-update-notice-notice",
                    "label": "Update notice",
                    "updated": {"date-parts": [[2024, 10, 10]]}
                }
            ]
        }
    },
    "10.1002/adma.202000000": {
        "status": "ok",
        "message": {
            "DOI": "10.1002/adma.202000000",
            "title": ["Mock Adma 2020 Article"],
            "publisher": "Wiley",
            "updated-by": [
                {
                    "type": "correction",
                    "DOI": "10.1002/adma.202000000-corr",
                    "label": "Correction to Adma Article",
                    "updated": {"date-parts": [[2024, 5, 1]]}
                }
            ]
        }
    }
}


def _safe_filename(doi: str) -> str:
    """Convert DOI to a safe filename."""
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", doi) + ".json"


def fetch_crossref_work(
    doi: str,
    allow_network: bool = False,
    cache_dir: Path | str | None = None,
    mailto: str | None = None,
) -> dict[str, Any]:
    """Fetch metadata for a DOI from Crossref or local cache/fixture.

    Args:
        doi: Normalized DOI string.
        allow_network: If True, allows querying Crossref Works API over HTTP.
        cache_dir: Custom cache directory path.
        mailto: Optional email to include in request for the Polite Pool.

    Returns:
        JSON response body parsed as a dictionary.

    Raises:
        CrossrefNotFoundError: DOI was not found (404).
        CrossrefRateLimitError: Rate limit exceeded (429).
        CrossrefClientError: Other network or parsing failures.
    """
    # 1. Resolve cache directory
    if cache_dir is None:
        resolved_cache_dir = DEFAULT_CACHE_DIR
    else:
        resolved_cache_dir = Path(cache_dir)

    safe_file = resolved_cache_dir / _safe_filename(doi)

    # 2. Check local file cache first
    if safe_file.exists():
        try:
            data = json.loads(safe_file.read_text(encoding="utf-8"))
            data["_cache_hit"] = True
            return data
        except json.JSONDecodeError:
            # If cache file is corrupt, we'll continue to network/mock
            pass

    # 3. Check mock fixtures
    if doi in MOCK_FIXTURES:
        data = MOCK_FIXTURES[doi].copy()
        data["_cache_hit"] = False
        return data

    # 4. Handle offline mode
    if not allow_network:
        raise CrossrefClientError(
            f"Network lookup is disabled. No mock fixture or cached metadata for DOI '{doi}'."
        )

    # 5. Perform HTTP request using urllib
    url = f"https://api.crossref.org/works/{doi}"
    if mailto:
        url += f"?mailto={mailto}"

    ua = f"ResearchIntegrityEvidenceReviewAgent/0.4 (mailto:{mailto})" if mailto else USER_AGENT
    req = urllib.request.Request(
        url,
        headers={"User-Agent": ua}
    )

    try:
        # 10 seconds timeout
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            
            # Write to cache
            resolved_cache_dir.mkdir(parents=True, exist_ok=True)
            safe_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            
            # Add cache miss flag and rate limit headers if present
            data["_cache_hit"] = False
            
            limit = response.headers.get("x-rate-limit-limit")
            interval = response.headers.get("x-rate-limit-interval")
            if limit:
                data["_x_rate_limit_limit"] = limit
            if interval:
                data["_x_rate_limit_interval"] = interval
            
            return data
            
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise CrossrefNotFoundError(f"DOI '{doi}' not found on Crossref.") from e
        elif e.code == 429:
            retry_after = e.headers.get("Retry-After")
            limit = e.headers.get("x-rate-limit-limit")
            interval = e.headers.get("x-rate-limit-interval")
            msg = "Crossref rate limit exceeded."
            if retry_after:
                msg += f" Retry-After: {retry_after} seconds."
            if limit:
                msg += f" Limit: {limit}."
            if interval:
                msg += f" Interval: {interval}."
            raise CrossrefRateLimitError(msg) from e
        else:
            raise CrossrefClientError(f"Crossref API returned HTTP error status: {e.code}") from e
    except urllib.error.URLError as e:
        raise CrossrefClientError(f"Failed to connect to Crossref API: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise CrossrefClientError(f"Failed to parse JSON response from Crossref: {e}") from e
    except Exception as e:
        raise CrossrefClientError(f"Unexpected error fetching Crossref metadata: {e}") from e
