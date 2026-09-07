"""Small, deterministic HTTP client used by the clawq CLI."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4


EXIT_CONNECTION = 3
EXIT_TIMEOUT = 4
EXIT_API_CLIENT = 5
EXIT_API_SERVER = 6
EXIT_INVALID_RESPONSE = 7


@dataclass
class CliError(Exception):
    """A machine-readable failure with a stable process exit code."""

    code: str
    message: str
    exit_code: int
    status_code: int | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def as_dict(self) -> dict[str, Any]:
        details: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.status_code is not None:
            details["status_code"] = self.status_code
        if self.request_id:
            details["request_id"] = self.request_id
        return {"error": details}


class ApiClient:
    """Read-only client scoped to the API root, normally ``.../api``."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 15.0,
        opener=None,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        parsed_url = urlsplit(normalized_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("API URL must start with http:// or https://")
        if parsed_url.username or parsed_url.password:
            raise ValueError("API URL must not contain embedded credentials")
        if parsed_url.query or parsed_url.fragment:
            raise ValueError("API URL must not contain a query string or fragment")
        if timeout_seconds <= 0:
            raise ValueError("timeout must be greater than zero")
        self.base_url = normalized_url
        self.timeout_seconds = timeout_seconds
        self._opener = opener or urlopen

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        request_id = str(uuid4())
        query = urlencode(params or {})
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "clawq/0.1",
                "X-Request-ID": request_id,
            },
            method="GET",
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                status_code = response.getcode()
                headers = response.headers
                reason = getattr(response, "reason", "")
                body = response.read()
        except HTTPError as exc:
            status_code = exc.code
            headers = exc.headers
            reason = str(exc.reason or "")
            body = exc.read()
        except (socket.timeout, TimeoutError) as exc:
            raise CliError(
                code="request_timeout",
                message=f"request exceeded {self.timeout_seconds:g} seconds",
                exit_code=EXIT_TIMEOUT,
                request_id=request_id,
            ) from exc
        except (URLError, OSError) as exc:
            raise CliError(
                code="connection_error",
                message=str(exc) or "unable to connect to claw-quant-data",
                exit_code=EXIT_CONNECTION,
                request_id=request_id,
            ) from exc

        response_request_id = headers.get("X-Request-ID") or request_id
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise CliError(
                code="invalid_response",
                message="server returned a non-JSON response",
                exit_code=EXIT_INVALID_RESPONSE,
                status_code=status_code,
                request_id=response_request_id,
            ) from exc

        if status_code >= 400:
            remote_error = payload.get("error", {}) if isinstance(payload, dict) else {}
            code = remote_error.get("code") or f"http_{status_code}"
            message = remote_error.get("message") or reason or "request failed"
            raise CliError(
                code=str(code),
                message=str(message),
                exit_code=(
                    EXIT_API_CLIENT if status_code < 500 else EXIT_API_SERVER
                ),
                status_code=status_code,
                request_id=remote_error.get("request_id") or response_request_id,
            )
        return payload
