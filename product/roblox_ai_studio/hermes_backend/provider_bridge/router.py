"""Router for selecting provider accounts based on intent and health."""

import random
from dataclasses import dataclass
from typing import Literal

from .accounts import is_account_valid
from .config import ProviderAccount, ProviderConfig
from .health import HealthRegistry

@dataclass
class GenerationRouteRequest:
    task: Literal["plan", "generate_luau", "review", "repair", "summarize"]
    quality: Literal["fast", "balanced", "high"]
    preferred_provider: str | None = None
    preferred_model: str | None = None

class ProviderRouter:
    def __init__(self, config: ProviderConfig, health_registry: HealthRegistry | None = None):
        self.config = config
        self.health = health_registry or HealthRegistry()

    def select(self, request: GenerationRouteRequest) -> ProviderAccount | None:
        candidates = [acc for acc in self.config.accounts if is_account_valid(acc) and self.health.get(acc.id).is_healthy()]
        
        if not candidates:
            return None

        # 1. Preferred provider
        if request.preferred_provider:
            for acc in candidates:
                if acc.provider == request.preferred_provider or acc.id == request.preferred_provider:
                    return acc

        # 2. Preserve the requested quality hook; account metadata is not available yet.
        quality_filtered = candidates

        # 3. Round robin / random choice
        return random.choice(quality_filtered)

    def record_success(self, account_id: str, usage: dict) -> None:
        self.health.get(account_id).record_success()

    def record_failure(self, account_id: str, error: Exception) -> None:
        self.health.get(account_id).record_error(str(error))
