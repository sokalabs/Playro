import pytest

from product.roblox_ai_studio.hermes_backend.provider_bridge.config import (
    ProviderAccount,
    safe_endpoint_for_display,
    validate_provider_endpoint,
)

def test_provider_account_redaction():
    account = ProviderAccount(
        id="test-1",
        provider="openai",
        display_name="My OpenAI",
        auth_type="api_key",
        endpoint=None,
        model_aliases={},
        _secret="sk-secret1234567890"
    )
    safe_dict = account.to_safe_dict()
    assert safe_dict["id"] == "test-1"
    assert "_secret" not in safe_dict
    assert "secret" not in str(safe_dict)
    
    # Test representation as well
    assert "sk-secret" not in repr(account)
    print("test_provider_account_redaction passed")

def test_provider_endpoint_display_strips_sensitive_parts():
    endpoint = "https://" + "user:secret@" + "example.com:8443/v1?api_key=abc#token"
    assert safe_endpoint_for_display(endpoint) == "https://example.com:8443/v1"

def test_provider_endpoint_display_hides_unsafe_hosts_by_default():
    assert safe_endpoint_for_display("https://metadata/v1") is None
    assert safe_endpoint_for_display("https://192.168.1.10/v1") is None
    assert safe_endpoint_for_display("http://api.example.com/v1") is None
    assert safe_endpoint_for_display("http://localhost:11434/v1") is None

def test_provider_endpoint_display_can_show_loopback_proxy():
    assert (
        safe_endpoint_for_display("http://localhost:11434/v1?token=hidden", allow_local=True)
        == "http://localhost:11434/v1"
    )

def test_provider_endpoint_validation_blocks_unsafe_remote_urls():
    with pytest.raises(ValueError):
        validate_provider_endpoint("https://" + "user:secret@" + "example.com/v1")
    with pytest.raises(ValueError):
        validate_provider_endpoint("https://api.example.com/v1?api_key=abc")
    with pytest.raises(ValueError):
        validate_provider_endpoint("http://api.example.com/v1")
    with pytest.raises(ValueError):
        validate_provider_endpoint("https://127.0.0.1:8080/v1")
    with pytest.raises(ValueError):
        validate_provider_endpoint("https://metadata/v1")
    with pytest.raises(ValueError):
        validate_provider_endpoint("https://models.internal/v1")
    assert validate_provider_endpoint("https://api.example.com/v1/") == "https://api.example.com/v1"

def test_provider_endpoint_validation_allows_loopback_proxy_only_when_requested():
    assert (
        validate_provider_endpoint("http://localhost:11434/v1/", allow_local=True)
        == "http://localhost:11434/v1"
    )
    assert (
        validate_provider_endpoint("https://[::1]:11434/v1/", allow_local=True)
        == "https://[::1]:11434/v1"
    )
    with pytest.raises(ValueError):
        validate_provider_endpoint("http://192.168.1.10:11434/v1", allow_local=True)
    with pytest.raises(ValueError):
        validate_provider_endpoint("http://api.example.com/v1", allow_local=True)


def test_local_proxy_endpoint_validation_rejects_non_loopback_hostnames():
    # `allow_local=True` is only for explicit smoke/local proxy accounts. It
    # must not become a general HTTP escape hatch for LAN, DNS, or metadata
    # service endpoints.
    for endpoint in (
        "http://host.docker.internal:11434/v1",
        "http://models.local:11434/v1",
        "http://metadata.google.internal/v1",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5:11434/v1",
        "http://[fd00::1]:11434/v1",
    ):
        with pytest.raises(ValueError):
            validate_provider_endpoint(endpoint, allow_local=True)

if __name__ == "__main__":
    test_provider_account_redaction()
