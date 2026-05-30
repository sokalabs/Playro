"""Account abstractions and validation for provider routing."""

from .config import ProviderAccount, validate_provider_endpoint

def is_account_valid(account: ProviderAccount) -> bool:
    """Basic validation for account sanity."""
    if not account.enabled:
        return False
    if account.auth_type == "api_key" and not account._secret:
        return False
    if account.auth_type == "local_proxy" and not account.endpoint:
        return False
    try:
        validate_provider_endpoint(account.endpoint, allow_local=account.auth_type == "local_proxy")
    except ValueError:
        return False
    return True
