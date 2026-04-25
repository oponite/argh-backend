import httpx
from app.core.config import NBA_HEADERS, DEFAULT_TIMEOUT

class ClientManager:
    _client: httpx.AsyncClient | None = None

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(headers=NBA_HEADERS, timeout=DEFAULT_TIMEOUT)
        return cls._client

    @classmethod
    async def close_client(cls):
        if cls._client is not None and not cls._client.is_closed:
            await cls._client.aclose()
            cls._client = None

def get_http_client() -> httpx.AsyncClient:
    return ClientManager.get_client()
