"""HTTP client with retry logic and SSE streaming for live tests."""

from __future__ import annotations

import http.client
import json
import select
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Generator


class LiveResponse:
    """Represents an API response."""

    def __init__(self, status: int | None, body: str, error: str | None = None):
        self.status = status
        self.body = body
        self.error = error

    @property
    def ok(self) -> bool:
        return self.status == 200 and not self.error

    @property
    def json(self) -> Any:
        if self.body:
            return json.loads(self.body)
        return None

    def __repr__(self) -> str:
        return f"LiveResponse(status={self.status}, error={self.error!r})"


def http_get(
    url: str, headers: dict, timeout: int = 30, retries: int = 1
) -> LiveResponse:
    """HTTP GET with retries."""
    last_err = None
    for attempt in range(retries + 1):
        if attempt > 0:
            time.sleep(0.5 * attempt)
        req = urllib.request.Request(url, headers=headers, method="GET")
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return LiveResponse(resp.status, resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else ""
            last_err = f"HTTP {e.code}: {e.reason}"
            if attempt == retries:
                return LiveResponse(e.code, err_body, last_err)
        except Exception as e:
            last_err = str(e)
            if attempt == retries:
                return LiveResponse(None, "", last_err)
    return LiveResponse(None, "", last_err)


def http_post(
    url: str, headers: dict, body: dict, timeout: int = 120, retries: int = 1
) -> LiveResponse:
    """HTTP POST with retries."""
    data = json.dumps(body).encode("utf-8")
    last_err = None
    for attempt in range(retries + 1):
        if attempt > 0:
            time.sleep(1.0 * attempt)
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return LiveResponse(resp.status, resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else ""
            last_err = f"HTTP {e.code}: {e.reason}"
            if attempt == retries:
                return LiveResponse(e.code, err_body, last_err)
        except Exception as e:
            last_err = str(e)
            if attempt == retries:
                return LiveResponse(None, "", last_err)
    return LiveResponse(None, "", last_err)


def http_post_stream(
    url: str,
    headers: dict,
    body: dict,
    timeout: int = 120,
) -> Generator[tuple[int | None, str, str | None], None, None]:
    """HTTP POST streaming with SSE line-by-line reading.

    Yields (status, line, error) tuples for each SSE event.
    """
    data = json.dumps(body).encode("utf-8")
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query

    ctx = ssl.create_default_context()
    conn = None
    try:
        if parsed.scheme == "https":
            conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)

        conn.request("POST", path, body=data, headers=headers)
        resp = conn.getresponse()
        status = resp.status

        if status >= 400:
            err_body = resp.read().decode("utf-8")
            yield status, err_body, f"HTTP {status}"
            return

        fp = resp.fp
        received_stop = False
        idle_timeout = 10.0
        while True:
            ready, _, _ = select.select([fp], [], [], idle_timeout)
            if not ready:
                yield status, "", f"stream timeout ({idle_timeout}s no data)"
                return

            line = fp.readline()
            if not line:
                break

            line_str = line.decode("utf-8").rstrip("\n").rstrip("\r")
            yield status, line_str, None

            if '"message_stop"' in line_str or "data: [DONE]" in line_str:
                received_stop = True
            if received_stop:
                idle_timeout = 3.0
            if received_stop and line_str == "":
                break
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        yield e.code, err_body, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        yield None, "", str(e)
    finally:
        if conn:
            conn.close()
