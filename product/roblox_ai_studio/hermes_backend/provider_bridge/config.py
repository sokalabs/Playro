"""Provider bridge config schema and account definitions."""

import ipaddress
import json
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

ALLOWED_ENDPOINT_SCHEMES = {"https"}
ALLOWED_LOCAL_ENDPOINT_SCHEMES = {"http", "https"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
PRIVATE_HOST_SUFFIXES = (".corp", ".home", ".internal", ".lan", ".local", ".localhost")

@dataclass
class ProviderAccount:
    id: str
    provider: Literal["openai", "codex", "gemini", "claude", "openai_compatible"]
    display_name: str
    auth_type: Literal["api_key", "oauth", "local_proxy"]
    endpoint: str | None
    model_aliases: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    _secret: str | None = field(default=None, repr=False)

    def to_safe_dict(self) -> dict:
        return {
            "id": self.id,
            "provider": self.provider,
            "display_name": self.display_name,
            "auth_type": self.auth_type,
            "endpoint": safe_endpoint_for_display(
                self.endpoint,
                allow_local=self.auth_type == "local_proxy",
            ),
            "model_aliases": self.model_aliases,
            "enabled": self.enabled,
        }

def safe_endpoint_for_display(endpoint: str | None, *, allow_local: bool = False) -> str | None:
    if not endpoint:
        return None
    parsed = urlsplit(endpoint.strip())
    if not parsed.scheme or not parsed.hostname:
        return None
    host = parsed.hostname or ""
    netloc = host
    if ":" in host and not host.startswith("["):
        netloc = f"[{host}]"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    display_endpoint = urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), "", ""))
    try:
        return validate_provider_endpoint(display_endpoint, allow_local=allow_local)
    except ValueError:
        return None


def validate_provider_endpoint(endpoint: str | None, *, allow_local: bool = False) -> str | None:
    if not endpoint:
        return None
    parsed = urlsplit(endpoint.strip())
    allowed_schemes = ALLOWED_LOCAL_ENDPOINT_SCHEMES if allow_local else ALLOWED_ENDPOINT_SCHEMES
    if parsed.scheme not in allowed_schemes or not parsed.hostname:
        if allow_local:
            raise ValueError("provider endpoint must be an HTTP(S) loopback URL")
        raise ValueError("provider endpoint must be an HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("provider endpoint must not include credentials, query, or fragment")
    host = parsed.hostname
    host_is_loopback = host in LOOPBACK_HOSTS
    host_is_ip = False
    try:
        ip = ipaddress.ip_address(host)
        host_is_ip = True
        host_is_loopback = host_is_loopback or ip.is_loopback
        if not allow_local and (ip.is_private or ip.is_loopback or ip.is_link_local):
            raise ValueError("provider endpoint must not target private IP ranges")
    except ValueError as exc:
        if "provider endpoint" in str(exc):
            raise
    if allow_local and not host_is_loopback:
        raise ValueError("local provider endpoint must target a loopback host")
    if not allow_local and host_is_loopback:
        raise ValueError("provider endpoint must not target loopback hosts")
    normalized_host = host.rstrip(".").lower()
    if not allow_local and not host_is_ip:
        if "." not in normalized_host or normalized_host.endswith(PRIVATE_HOST_SUFFIXES):
            raise ValueError("provider endpoint must target a public host")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


@dataclass
class ProviderConfig:
    accounts: list[ProviderAccount] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ProviderConfig":
        accounts = []
        for acc_data in data.get("accounts", []):
            secret = acc_data.pop("_secret", None) or acc_data.pop("secret", None)
            account = ProviderAccount(**acc_data, _secret=secret)
            accounts.append(account)
        return cls(accounts=accounts)

    def to_safe_dict(self) -> dict:
        return {
            "accounts": [acc.to_safe_dict() for acc in self.accounts]
        }
