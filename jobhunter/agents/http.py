"""How every company agent reads a site (stage 8, docs/agents/company-agents.md).

Read-only and polite: one request at a time, a short pause between requests to the same host,
an identifying User-Agent, and only the public JSON endpoints the sites' own pages use.

fetch_json  GET (or POST with a JSON body) -> parsed JSON.  fetch_text  GET a web page -> its HTML.
            Both raise FetchError when the site can't be read, so the caller can skip that company
            without marking anything as seen.
"""

import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

USER_AGENT = "JobHunter/1.0 (personal job search; read-only; one request at a time)"
TIMEOUT_SECONDS = 20
PAUSE_SECONDS = 1.0  # between two requests to the same host
RETRY_AFTER_SECONDS = 3.0
TOO_MANY_REQUESTS_WAIT = 30.0  # 429 without a Retry-After header (Qualcomm)
MAX_WAIT_SECONDS = 120.0

_last_request: dict[str, float] = {}  # host -> time.monotonic() of the last request
_pause_by_host: dict[str, float] = {}  # stricter sites get a longer pause (config: "pause_seconds")


def set_pause(host: str, seconds: float) -> None:
    """A longer pause between requests to one host (Microsoft answers 429 at one request per second)."""
    _pause_by_host[host] = seconds


class FetchError(Exception):
    """The site could not be read (network error, HTTP error, or a body that isn't JSON)."""


def _wait_for_turn(host: str) -> None:
    last = _last_request.get(host)
    if last is not None:
        wait = _pause_by_host.get(host, PAUSE_SECONDS) - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request[host] = time.monotonic()


def _request_once(url: str, body: bytes | None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9, */*;q=0.8"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    _wait_for_turn(urlsplit(url).netloc)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return resp.read()


def _too_many_requests_wait(e: urllib.error.HTTPError) -> float:
    """How long a 429 asks us to wait: its Retry-After header (seconds), else 30s, never more than 2 minutes."""
    try:
        seconds = float((e.headers or {}).get("Retry-After") or TOO_MANY_REQUESTS_WAIT)
    except ValueError:  # Retry-After can also be a date; then just use the default
        seconds = TOO_MANY_REQUESTS_WAIT
    return min(max(seconds, 0), MAX_WAIT_SECONDS)


def _fetch(url: str, body: bytes | None) -> bytes:
    """One retry on a network error, a 5xx, or a 429 (after the wait the site asks for). Any other 4xx is final."""
    for attempt in (1, 2):
        wait = RETRY_AFTER_SECONDS
        try:
            return _request_once(url, body)
        except urllib.error.HTTPError as e:
            retryable = e.code >= 500 or e.code == 429
            if not retryable or attempt == 2:
                raise FetchError(f"HTTP {e.code} from {url}") from e
            if e.code == 429:
                wait = _too_many_requests_wait(e)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == 2:
                raise FetchError(f"network error from {url}: {e}") from e
        time.sleep(wait)
    raise AssertionError("unreachable")


def fetch_json(url: str, data: dict | None = None):
    """GET `url`, or POST `data` as JSON -> parsed JSON (403 = blocked, final)."""
    raw = _fetch(url, json.dumps(data).encode("utf-8") if data is not None else None)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise FetchError(f"not JSON from {url}") from e


def fetch_text(url: str) -> str:
    """GET a web page -> its HTML (for sites that put their data inside the page, like Apple)."""
    return _fetch(url, None).decode("utf-8", "replace")
