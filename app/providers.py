"""Data providers. Olostep = main layer, Crustdata = second source."""
import asyncio
import os
from urllib.parse import urlparse

import httpx

OFFICIAL_SUFFIXES = (".gov.in", ".nic.in")
SEED_URLS = ["https://scholarships.gov.in/"]  # reliable fallback


def is_official(url: str) -> bool:
    return (urlparse(url).hostname or "").endswith(OFFICIAL_SUFFIXES)


async def fetch_page(url: str) -> str:
    """Olostep scrape -> markdown. POST /v1/scrapes (url_to_scrape, formats)."""
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(
            "https://api.olostep.com/v1/scrapes",
            headers={"Authorization": f"Bearer {os.environ['OLOSTEP_API_KEY']}"},
            json={"url_to_scrape": url, "formats": ["markdown"]},
        )
        r.raise_for_status()
        # Big pages may come back as a hosted URL instead of inline content.
        return (r.json().get("result") or {}).get("markdown_content") or ""


async def olostep_discover(query: str, limit: int) -> list[str]:
    from olostep import AsyncOlostep  # official SDK
    async with AsyncOlostep(api_key=os.environ["OLOSTEP_API_KEY"]) as client:
        res = await client.searches.create(query=query, limit=limit * 3)
    urls = []
    for link in res.links:  # VERIFY field name against the SDK docs
        u = getattr(link, "url", None) or (link.get("url") if isinstance(link, dict) else None)
        if u:
            urls.append(u)
    return urls


async def crustdata_discover(query: str, limit: int) -> list[str]:
    """TODO: call Crustdata Web Search API (docs.crustdata.com) with
    CRUSTDATA_API_KEY and return result URLs. Empty until wired."""
    return []


async def discover(query: str, limit: int = 4) -> list[str]:
    results = await asyncio.gather(
        olostep_discover(query, limit), crustdata_discover(query, limit),
        return_exceptions=True,
    )
    urls: list[str] = []
    for r in results:
        if not isinstance(r, Exception):
            urls += r
    official = [u for u in dict.fromkeys(urls) if is_official(u)][:limit]
    return official or SEED_URLS
