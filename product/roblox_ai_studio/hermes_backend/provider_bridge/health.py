"""Health and quota tracking for provider accounts."""

import time
from dataclasses import dataclass, field

@dataclass
class AccountHealth:
    account_id: str
    error_count: int = 0
    last_error_time: float = 0.0
    last_error_msg: str | None = None
    is_rate_limited: bool = False
    rate_limit_reset: float = 0.0

    def record_error(self, message: str, rate_limit_seconds: int = 0) -> None:
        self.error_count += 1
        self.last_error_time = time.time()
        self.last_error_msg = message
        if rate_limit_seconds > 0:
            self.is_rate_limited = True
            self.rate_limit_reset = time.time() + rate_limit_seconds

    def record_success(self) -> None:
        self.error_count = 0
        self.last_error_time = 0.0
        self.last_error_msg = None
        self.is_rate_limited = False
        self.rate_limit_reset = 0.0

    def is_healthy(self) -> bool:
        if self.is_rate_limited:
            if time.time() > self.rate_limit_reset:
                self.is_rate_limited = False
            else:
                return False
        # Simple backoff: if errors > 3, wait 5 mins
        if self.error_count > 3:
            if time.time() - self.last_error_time < 300:
                return False
        return True

class HealthRegistry:
    def __init__(self):
        self._health: dict[str, AccountHealth] = {}

    def get(self, account_id: str) -> AccountHealth:
        if account_id not in self._health:
            self._health[account_id] = AccountHealth(account_id=account_id)
        return self._health[account_id]
