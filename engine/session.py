import httpx

NSE_HOME = "https://www.nseindia.com"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.nseindia.com/",
}


class NseSession:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(headers=_HEADERS, follow_redirects=True)
        await self.refresh()

    async def refresh(self) -> None:
        if self._client is None:
            raise RuntimeError("Session not initialized — call initialize() first")
        await self._client.get(NSE_HOME)

    async def get(self, url: str, **kwargs) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("Session not initialized — call initialize() first")
        return await self._client.get(url, **kwargs)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "NseSession":
        await self.initialize()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()
