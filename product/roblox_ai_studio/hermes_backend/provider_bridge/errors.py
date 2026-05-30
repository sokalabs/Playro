class ProviderError(Exception):
    pass

class ProviderRateLimitError(ProviderError):
    pass
