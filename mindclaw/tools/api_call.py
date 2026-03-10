# input: tools/base.py, tools/_ssrf.py, httpx, mindclaw.config.schema.AuthProfileConfig
# output: 导出 ApiCallTool
# pos: HTTP API 调用工具，支持 auth profile 注入和 URL 白名单
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import base64
import posixpath
from urllib.parse import unquote, urlparse, urlunparse

import httpx
from loguru import logger

from mindclaw.config.schema import AuthProfileConfig

from ._ssrf import is_safe_url as _is_safe_url
from .base import RiskLevel, Tool

_ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "DELETE"})
_TIMEOUT_SECONDS = 30.0


def _build_auth_header(profile: AuthProfileConfig) -> dict[str, str]:
    """Return the header dict for a given auth profile.

    The raw credential value is NEVER returned in error messages or responses.
    """
    ptype = profile.profile_type.lower()
    if ptype == "bearer":
        return {"Authorization": f"Bearer {profile.value}"}
    if ptype == "header":
        return {profile.header_name: profile.value}
    if ptype == "basic":
        encoded = base64.b64encode(profile.value.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    return {}


class ApiCallTool(Tool):
    name = "api_call"
    description = (
        "Make an authenticated HTTP API call. "
        "URL must be in the configured allowlist. "
        "Use auth_profile to inject credentials without exposing tokens."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL to call (must match an allowlist prefix)",
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE"],
                "description": "HTTP method (default: GET)",
            },
            "headers": {
                "type": "object",
                "description": "Additional request headers (optional)",
            },
            "body": {
                "type": "string",
                "description": "Request body as a string (for POST/PUT)",
            },
            "auth_profile": {
                "type": "string",
                "description": "Name of a configured auth profile to inject credentials",
            },
        },
        "required": ["url"],
    }
    risk_level = RiskLevel.DANGEROUS
    max_result_chars: int = 5000

    def __init__(
        self,
        url_allowlist: list[str],
        auth_profiles: dict[str, AuthProfileConfig],
        max_chars: int = 5000,
    ) -> None:
        self._url_allowlist = url_allowlist
        self._auth_profiles = auth_profiles
        self.max_result_chars = max_chars

    # ── Validation helpers ────────────────────────────────────────────────

    @staticmethod
    def _sanitize_url_for_display(url: str) -> str:
        """Strip userinfo (user:password@) from URL for safe display."""
        p = urlparse(url)
        if p.username or p.password:
            safe_netloc = p.hostname or ""
            if p.port:
                safe_netloc += f":{p.port}"
            return urlunparse(p._replace(netloc=safe_netloc))
        return url

    def _check_allowlist(self, url: str) -> str | None:
        """Return an error string if url is not allowed, else None.

        Uses urlparse with path normalization to prevent:
        - subdomain spoofing (e.g. api.example.comevil.tld)
        - path traversal (e.g. /v1/../../admin)
        - percent-encoded traversal (e.g. /v1/%2e%2e/admin)
        """
        if not self._url_allowlist:
            return "Error: URL not allowed — allowlist is empty (no URLs configured)"
        parsed_url = urlparse(url)
        norm_url_path = posixpath.normpath(unquote(parsed_url.path) or "/")
        for prefix in self._url_allowlist:
            parsed_prefix = urlparse(prefix)
            norm_prefix_path = posixpath.normpath(
                unquote(parsed_prefix.path) or "/"
            )
            if (
                parsed_url.scheme == parsed_prefix.scheme
                and parsed_url.netloc == parsed_prefix.netloc
                and (
                    norm_url_path == norm_prefix_path
                    or norm_url_path.startswith(
                        norm_prefix_path.rstrip("/") + "/"
                    )
                )
            ):
                return None
        safe_url = self._sanitize_url_for_display(url)
        return f"Error: URL not allowed by allowlist: {safe_url}"

    def _check_method(self, method: str) -> str | None:
        """Return an error string if method is invalid, else None."""
        if method.upper() not in _ALLOWED_METHODS:
            return f"Error: invalid HTTP method '{method}' — must be one of GET, POST, PUT, DELETE"
        return None

    # ── Execute ───────────────────────────────────────────────────────────

    async def execute(self, params: dict) -> str:
        url = params.get("url", "")
        method = params.get("method", "GET").upper()
        extra_headers: dict[str, str] = dict(params.get("headers") or {})
        body: str | None = params.get("body")
        auth_profile_name: str | None = params.get("auth_profile")

        # 1. Method validation
        method_err = self._check_method(method)
        if method_err:
            return method_err

        # 2. URL allowlist check (prefix-based, evaluated before DNS resolution)
        allowlist_err = self._check_allowlist(url)
        if allowlist_err:
            return allowlist_err

        # 3. SSRF check (resolves DNS)
        if not _is_safe_url(url):
            return "Error: URL targets a private/internal address"

        # 4. Auth profile injection
        if auth_profile_name is not None:
            profile = self._auth_profiles.get(auth_profile_name)
            if profile is None:
                return f"Error: auth profile '{auth_profile_name}' not found"
            auth_headers = _build_auth_header(profile)
            extra_headers = {**extra_headers, **auth_headers}

        # 5. Execute request — no redirects, fixed timeout
        logger.info(f"api_call: {method} {self._sanitize_url_for_display(url)}")
        try:
            async with httpx.AsyncClient(
                follow_redirects=False,
                timeout=_TIMEOUT_SECONDS,
                trust_env=False,
            ) as client:
                response = await client.request(
                    method,
                    url,
                    headers=extra_headers if extra_headers else None,
                    content=body,
                )
        except Exception as exc:
            return f"Error: request failed — {type(exc).__name__}"

        # 6. Format response (selected headers + body)
        selected_headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() in ("content-type", "x-request-id", "x-ratelimit-remaining")
        }
        body_text = response.text
        formatted = (
            f"Status: {response.status_code}\n"
            f"Headers: {selected_headers}\n\n"
            f"{body_text}"
        )

        # 7. Truncate
        if len(formatted) > self.max_result_chars:
            formatted = formatted[: self.max_result_chars] + "\n...(truncated)"

        return formatted
