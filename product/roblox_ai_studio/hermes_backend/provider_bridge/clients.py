from typing import List, Dict, Any
from .config import ProviderAccount, validate_provider_endpoint

class OpenAIAccountAdapter:
    def __init__(self, account: ProviderAccount):
        self.account = account
        
    def build_chat_request(self, messages: List[Dict[str, str]], model: str) -> Dict[str, Any]:
        allow_local = self.account.auth_type == "local_proxy"
        if allow_local and not self.account.endpoint:
            raise ValueError("local proxy accounts require an endpoint")
        base_url = (
            validate_provider_endpoint(self.account.endpoint, allow_local=allow_local)
            or "https://api.openai.com/v1"
        )
            
        headers = {
            "Content-Type": "application/json"
        }
        
        # Don't log secrets, but add them to headers
        if self.account._secret:
            headers["Authorization"] = f"Bearer {self.account._secret}"
            
        resolved_model = self.account.model_aliases.get(model, model)
            
        return {
            "url": f"{base_url}/chat/completions",
            "headers": headers,
            "json": {
                "model": resolved_model,
                "messages": messages
            }
        }
