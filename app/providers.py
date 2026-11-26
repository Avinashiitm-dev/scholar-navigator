"""Data providers. Olostep = main layer, Crustdata = second source."""
import asyncio
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx

OFFICIAL_SUFFIXES = (".gov.in", ".nic.in")
SEED_URLS = ["https://scholarships.gov.in/"]  # reliable fallback
DEFAULT_CACHE_DIR = Path(".cache/pages")


def is_official(url: str) -> bool:
    return (urlparse(url).hostname or "").endswith(OFFICIAL_SUFFIXES)


def _cache_path(url: str, cache_dir: Path | None = None) -> Path:
    base = cache_dir or Path(os.environ.get("PAGE_CACHE_DIR") or DEFAULT_CACHE_DIR)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return base / f"{digest}.md"


def _should_bypass_cache(bypass_cache: bool | None) -> bool:
    if bypass_cache is not None:
        return bypass_cache
    return os.environ.get("BYPASS_PAGE_CACHE", "").strip().lower() in ("1", "true", "yes")


async def fetch_page(
    url: str,
    bypass_cache: bool | None = None,
    cache_dir: Path | None = None,
) -> str:
    """Olostep scrape -> markdown via raw REST, with URL-hashed disk cache.

    The API returns result.markdown_content inline for most pages.
    For large pages it sets markdown_content=null and provides
    result.markdown_hosted_url instead; we fetch that URL to get the content.

    Cached pages are stored under ``PAGE_CACHE_DIR`` (default ``.cache/pages``)
    keyed by SHA-256 of the URL. Set ``bypass_cache=True`` or env var
    ``BYPASS_PAGE_CACHE=1`` to skip reading from the cache and fetch fresh.
    """
    bypass = _should_bypass_cache(bypass_cache)
    cache_file = _cache_path(url, cache_dir)
    if not bypass and cache_file.is_file():
        return cache_file.read_text(encoding="utf-8")

    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(
            "https://api.olostep.com/v1/scrapes",
            headers={"Authorization": f"Bearer {os.environ['OLOSTEP_API_KEY']}"},
            json={"url_to_scrape": url, "formats": ["markdown"]},
        )
        r.raise_for_status()
        result = (r.json().get("result") or {})
        content = result.get("markdown_content") or ""
        if not content:
            # Large page: content was offloaded to a hosted URL
            hosted_url = result.get("markdown_hosted_url") or ""
            if hosted_url:
                hosted = await c.get(hosted_url, follow_redirects=True)
                hosted.raise_for_status()
                content = hosted.text

    if content:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(content, encoding="utf-8")
    return content


async def olostep_discover(query: str, limit: int) -> list[str]:
    """Use the official olostep SDK to search the web.

    SearchesResult.links is a list of dicts (each with key "url")
    produced by SearchLink.model_dump() inside the SDK.
    """
    from olostep import AsyncOlostep  # official SDK
    async with AsyncOlostep(api_key=os.environ["OLOSTEP_API_KEY"]) as client:
        res = await client.searches.create(query=query, limit=limit * 3)
    urls = []
    for link in res.links:  # each element is a dict from model_dump()
        u = link.get("url") if isinstance(link, dict) else getattr(link, "url", None)
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
