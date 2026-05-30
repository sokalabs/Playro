from product.roblox_ai_studio.hermes_backend.provider_bridge.config import ProviderAccount, ProviderConfig
from product.roblox_ai_studio.hermes_backend.provider_bridge.router import ProviderRouter, GenerationRouteRequest
from product.roblox_ai_studio.hermes_backend.provider_bridge.health import HealthRegistry

def test_router_failover_and_preferred():
    accounts = [
        ProviderAccount(id="a1", provider="openai", display_name="O1", auth_type="api_key", endpoint=None, _secret="test"),
        ProviderAccount(id="a2", provider="openai", display_name="O2", auth_type="api_key", endpoint=None, _secret="test")
    ]
    config = ProviderConfig(accounts=accounts)
    registry = HealthRegistry()
    router = ProviderRouter(config, registry)
    
    # Mark a1 as failed multiple times to trigger unhealthy status
    for _ in range(4):
        router.record_failure("a1", Exception("Quota exceeded"))
    
    req = GenerationRouteRequest(task="plan", quality="high", preferred_provider="openai")
    selected = router.select(req)
    
    # Should skip a1 and select a2 due to failover
    assert selected.id == "a2"
    print("test_router_failover_and_preferred passed")

if __name__ == "__main__":
    test_router_failover_and_preferred()
