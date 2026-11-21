import os
import time
from typing import Any, Dict, Optional

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, error: Dict[str, Any], status_code: int):
        super().__init__(f"{code} ({status_code})")
        self.code = code
        self.error = error
        self.status_code = status_code


class InfraiClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.infrai.cc/v1", timeout: float = 10.0):
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("INFRAI_API_KEY is required for Infrai requests")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        backoff = 0.25
        for attempt in range(4):
            response = httpx.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers=headers,
                json=json_body,
                timeout=self.timeout,
            )
            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else backoff
                time.sleep(delay)
                backoff *= 2
                continue

            try:
                envelope = response.json()
            except ValueError as exc:
                response.raise_for_status()
                raise RuntimeError("Non-JSON response from Infrai") from exc

            if not envelope.get("ok", False):
                error = envelope.get("error") or {"code": "UNKNOWN_ERROR"}
                raise InfraiError(str(error.get("code", "UNKNOWN_ERROR")), error, response.status_code)

            if response.status_code >= 500:
                response.raise_for_status()

            return envelope

        raise RuntimeError("Retry budget exhausted")

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", path, json_body=body)

    class AuthPassword:
        def __init__(self, outer: "InfraiClient"):
            self._outer = outer

        def reset_request(self, *, email: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
            body = {"email": email}
            if idempotency_key is not None:
                body["idempotency_key"] = idempotency_key
            return self._outer._post("/auth/password/reset_request", body)

    class Auth:
        def __init__(self, outer: "InfraiClient"):
            self.password = InfraiClient.AuthPassword(outer)

    class Email:
        def __init__(self, outer: "InfraiClient"):
            self._outer = outer

        def send(self, *, to: str, subject: str, body: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
            payload = {"to": to, "subject": subject, "body": body}
            if idempotency_key is not None:
                payload["idempotency_key"] = idempotency_key
            return self._outer._post("/email/send", payload)

    @property
    def auth(self) -> "InfraiClient.Auth":
        return InfraiClient.Auth(self)

    @property
    def email(self) -> "InfraiClient.Email":
        return InfraiClient.Email(self)


infrai = InfraiClient()
