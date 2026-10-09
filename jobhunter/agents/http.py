"""How every company agent reads a site (stage 8, docs/agents/company-agents.md).

Read-only and polite: one request at a time, a short pause between requests to the same host,
an identifying User-Agent, and only the public JSON endpoints the sites' own pages use.

fetch_json  GET (or POST with a JSON body) -> parsed JSON. Raises FetchError when the site can't be read,
            so the caller can skip that company without marking anything as seen.
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

_last_request: dict[str, float] = {}  # host -> time.monotonic() of the last request


class FetchError(Exception):
    """The site could not be read (network error, HTTP error, or a body that isn't JSON)."""


def _wait_for_turn(host: str) -> None:
    last = _last_request.get(host)
    if last is not None:
        wait = PAUSE_SECONDS - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request[host] = time.monotonic()


def _request_once(url: str, body: bytes | None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    _wait_for_turn(urlsplit(url).netloc)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return resp.read()


def fetch_json(url: str, data: dict | None = None):
    """GET `url`, or POST `data` as JSON. One retry on a network error or a 5xx; a 4xx is final (403 = blocked)."""
    body = json.dumps(data).encode("utf-8") if data is not None else None
    for attempt in (1, 2):
        try:
            raw = _request_once(url, body)
            break
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 2:
                raise FetchError(f"HTTP {e.code} from {url}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == 2:
                raise FetchError(f"network error from {url}: {e}") from e
        time.sleep(RETRY_AFTER_SECONDS)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise FetchError(f"not JSON from {url}") from e
