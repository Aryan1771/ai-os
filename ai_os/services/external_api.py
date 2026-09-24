from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from ai_os.config import AiOsConfig


@dataclass(frozen=True)
class ExternalApiResult:
    ok: bool
    status_code: int | None
    data: object | None
    error: str = ""


def validate_external_url(url: str, config: AiOsConfig) -> str | None:
    parsed = urlparse(url)
    if not config.allow_external_apis:
        return "External APIs are disabled in ~/.ai_os/config.json."
    if parsed.scheme != "https" or not parsed.hostname:
        return "External API URLs must use HTTPS with a hostname."
    if parsed.hostname.lower() not in {host.lower() for host in config.allowed_api_hosts}:
        return f"Host is not allowlisted: {parsed.hostname}"
    return None


def post_external_json(
    url: str,
    payload: dict[str, object],
    *,
    config: AiOsConfig,
    headers: dict[str, str] | None = None,
    timeout_sec: int = 30,
) -> ExternalApiResult:
    error = validate_external_url(url, config)
    if error:
        return ExternalApiResult(False, None, None, error)
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers or {},
            timeout=max(1, int(timeout_sec)),
            allow_redirects=False,
        )
        response.raise_for_status()
        return ExternalApiResult(True, response.status_code, response.json())
    except (requests.RequestException, ValueError) as exc:
        return ExternalApiResult(False, None, None, str(exc))
