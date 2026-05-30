import pytest

from product.roblox_ai_studio.hermes_backend.provider_bridge.config import ProviderAccount
from product.roblox_ai_studio.hermes_backend.provider_bridge.clients import OpenAIAccountAdapter

def test_openai_adapter_request_format():
    account = ProviderAccount(
        id="test-1", 
        provider="openai_compatible", 
        display_name="Local Proxy", 
        auth_type="local_proxy", 
        endpoint="http://localhost:11434/v1",
        _secret=None
    )
    
    adapter = OpenAIAccountAdapter(account)
    req = adapter.build_chat_request(
        messages=[{"role": "user", "content": "Make an obby"}],
        model="gpt-4o-mini"
    )
    
    assert req["url"] == "http://localhost:11434/v1/chat/completions"
    assert req["json"]["model"] == "gpt-4o-mini"
    print("test_openai_adapter_request_format passed")

def test_openai_adapter_rejects_unsafe_api_key_endpoint():
    account = ProviderAccount(
        id="test-2",
        provider="openai_compatible",
        display_name="Unsafe Remote",
        auth_type="api_key",
        endpoint="http://api.example.com/v1?api_key=abc",
        _secret="sk-test",
    )

    adapter = OpenAIAccountAdapter(account)
    with pytest.raises(ValueError):
        adapter.build_chat_request(messages=[{"role": "user", "content": "Make an obby"}], model="gpt-4o-mini")

def test_openai_adapter_requires_local_proxy_endpoint():
    account = ProviderAccount(
        id="test-3",
        provider="openai_compatible",
        display_name="Missing Local Proxy",
        auth_type="local_proxy",
        endpoint=None,
        _secret=None,
    )

    adapter = OpenAIAccountAdapter(account)
    with pytest.raises(ValueError):
        adapter.build_chat_request(messages=[{"role": "user", "content": "Make an obby"}], model="gpt-4o-mini")

if __name__ == "__main__":
    test_openai_adapter_request_format()
