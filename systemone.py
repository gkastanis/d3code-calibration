# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""Small stdlib client for TypeSafe's System One API.

API documentation: https://docs.typesafe.ai/api.md. This module only sends a
request and returns its answers map; it does not implement rubric scoring.

Derived from `evals/semantic.py` in drupal/ai_best_practices, which implements
the `semantic_yes` rubric check on top of the same API, with the rubric-facing
half removed. Deliberate difference: that module puts up to 200 bytes of an HTTP
error body into its exception message, and the caller writes that message into
its results file. Nothing here echoes a response body, so a server that reflects
a request header cannot leak a key into a published file.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}


class SystemOneUnavailable(RuntimeError):
    """A usable System One answer could not be obtained."""


def api_key() -> str | None:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    try:
        return (Path.home() / ".config" / "typesafe" / "api.key").read_text().strip() or None
    except OSError:
        return None


def ask(state: object, questions: dict, *, key: str | None = None,
        url: str | None = None, model: str | None = None,
        timeout: float = 60, retries: int = 3) -> dict:
    """POST one request and return its ``answers`` dict.

    Retries transient HTTP failures and connection errors with exponential
    backoff. Configuration, authentication, and malformed replies raise
    SystemOneUnavailable.
    """
    key = key or api_key()
    if not key:
        raise SystemOneUnavailable(
            "no TYPESAFE_API_KEY in the environment and no ~/.config/typesafe/api.key")
    url = url or os.environ.get("TYPESAFE_API_URL", DEFAULT_URL)
    model = model or os.environ.get("TYPESAFE_MODEL", DEFAULT_MODEL)
    body = json.dumps({"state": state, "model": model, "questions": questions}).encode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    last = "no attempt made"
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode())
            if not isinstance(payload, dict) or not isinstance(payload.get("answers"), dict):
                raise SystemOneUnavailable("System One reply has no answers map")
            return payload["answers"]
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code not in RETRYABLE_STATUS:
                raise SystemOneUnavailable(last) from None
        except (urllib.error.URLError, TimeoutError,
                json.JSONDecodeError, UnicodeDecodeError) as exc:
            # A truncated or undecodable body is usually a flaky connection, so
            # it is retried rather than raised, matching the module this came from.
            last = type(exc).__name__
        if attempt < retries:
            time.sleep(1.5 * 2 ** attempt)
    raise SystemOneUnavailable(
        f"System One unreachable after {retries + 1} attempts: {last}")
