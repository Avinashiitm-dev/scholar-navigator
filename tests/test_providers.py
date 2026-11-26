"""Tests for the fixed providers module.

Covers:
1. olostep_discover – field name is res.links[i]["url"] (dict from model_dump())
2. fetch_page – falls back to markdown_hosted_url when markdown_content is null
3. is_official – domain-suffix checks

All network calls are mocked; no API keys required.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers import fetch_page, is_official, olostep_discover


# ---------------------------------------------------------------------------
# is_official
# ---------------------------------------------------------------------------

def test_is_official_gov_in():
    assert is_official("https://scholarships.gov.in/page")


def test_is_official_nic_in():
    assert is_official("https://pfms.nic.in/something")


def test_is_official_rejects_others():
    assert not is_official("https://example.com/scholarships")
    assert not is_official("https://gov.in.evil.com/")


# ---------------------------------------------------------------------------
# olostep_discover – links is a list of dicts with key "url"
# ---------------------------------------------------------------------------

class FakeSearchesResult:
    """Mimics SearchesResult as returned by the SDK (links = list of dicts)."""
    def __init__(self, links):
        self.links = links  # already list[dict], matching model_dump() output


class FakeSearchesMenu:
    def __init__(self, links):
        self._links = links

    async def create(self, query, *, limit=None, **kw):
        return FakeSearchesResult(self._links)


class FakeAsyncOlostep:
    """Minimal async context manager that stands in for AsyncOlostep."""
    def __init__(self, links):
        self.searches = FakeSearchesMenu(links)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _inject_fake_olostep(links):
    """Inject a fake ``olostep`` module so the lazy import inside olostep_discover
    resolves to our stub even when the real package is not installed.
    """
    import sys
    import types

    fake_olostep = types.ModuleType("olostep")
    fake_olostep.AsyncOlostep = lambda **kw: FakeAsyncOlostep(links)
    return patch.dict(sys.modules, {"olostep": fake_olostep})


@pytest.mark.asyncio
async def test_olostep_discover_dict_links():
    """SDK returns dicts; url must be read as link["url"]."""
    links = [
        {"url": "https://scholarships.gov.in/a", "title": "A"},
        {"url": "https://pfms.nic.in/b", "title": "B"},
        {"url": "https://example.com/c", "title": "C"},
    ]
    with _inject_fake_olostep(links), \
         patch("app.providers.os.environ", {"OLOSTEP_API_KEY": "test-key"}):
        urls = await olostep_discover("OBC scholarship Bihar", limit=4)
    assert "https://scholarships.gov.in/a" in urls
    assert "https://pfms.nic.in/b" in urls
    assert "https://example.com/c" in urls


@pytest.mark.asyncio
async def test_olostep_discover_no_url_key_skipped():
    """Dicts missing 'url' key are silently skipped."""
    links = [
        {"title": "No URL here"},
        {"url": "https://india.gov.in/valid"},
    ]
    with _inject_fake_olostep(links), \
         patch("app.providers.os.environ", {"OLOSTEP_API_KEY": "test-key"}):
        urls = await olostep_discover("test", limit=4)
    assert urls == ["https://india.gov.in/valid"]


# ---------------------------------------------------------------------------
# fetch_page – hosted URL fallback
# ---------------------------------------------------------------------------

def _make_scrape_response(result_dict):
    """Build a mock httpx response for the POST /v1/scrapes call."""
    r = MagicMock()
    r.json.return_value = {"result": result_dict}
    r.raise_for_status = MagicMock()
    return r


def _make_text_response(text):
    r = MagicMock()
    r.text = text
    r.raise_for_status = MagicMock()
    return r


@pytest.mark.asyncio
async def test_fetch_page_inline_markdown(tmp_path):
    """When markdown_content is present inline, return it directly."""
    scrape_resp = _make_scrape_response(
        {"markdown_content": "# Hello\nSome content", "markdown_hosted_url": None}
    )
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post = AsyncMock(return_value=scrape_resp)

    env = {"OLOSTEP_API_KEY": "test-key", "PAGE_CACHE_DIR": str(tmp_path)}
    with patch("app.providers.httpx.AsyncClient", return_value=mock_client), \
         patch("app.providers.os.environ", env):
        result = await fetch_page("https://scholarships.gov.in/")

    assert result == "# Hello\nSome content"
    mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_page_hosted_url_fallback(tmp_path):
    """When markdown_content is null, fetch from markdown_hosted_url."""
    hosted_content = "# Large page content " * 1000
    scrape_resp = _make_scrape_response({
        "markdown_content": None,
        "markdown_hosted_url": "https://api.olostep.com/v1/hosted/markdown_abc.md",
    })
    hosted_resp = _make_text_response(hosted_content)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post = AsyncMock(return_value=scrape_resp)
    mock_client.get = AsyncMock(return_value=hosted_resp)

    env = {"OLOSTEP_API_KEY": "test-key", "PAGE_CACHE_DIR": str(tmp_path)}
    with patch("app.providers.httpx.AsyncClient", return_value=mock_client), \
         patch("app.providers.os.environ", env):
        result = await fetch_page("https://scholarships.gov.in/big-page")

    assert result == hosted_content
    mock_client.get.assert_called_once_with(
        "https://api.olostep.com/v1/hosted/markdown_abc.md",
        follow_redirects=True,
    )


@pytest.mark.asyncio
async def test_fetch_page_no_content_no_hosted_url(tmp_path):
    """When both inline content and hosted URL are absent, return empty string."""
    scrape_resp = _make_scrape_response(
        {"markdown_content": None, "markdown_hosted_url": None}
    )
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post = AsyncMock(return_value=scrape_resp)

    env = {"OLOSTEP_API_KEY": "test-key", "PAGE_CACHE_DIR": str(tmp_path)}
    with patch("app.providers.httpx.AsyncClient", return_value=mock_client), \
         patch("app.providers.os.environ", env):
        result = await fetch_page("https://example.gov.in/empty")

    assert result == ""
    mock_client.get.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_fetch_page_writes_and_reads_disk_cache(tmp_path):
    """Second call for the same URL returns disk cache without calling HTTP."""
    scrape_resp = _make_scrape_response(
        {"markdown_content": "# Cached scheme", "markdown_hosted_url": None}
    )
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post = AsyncMock(return_value=scrape_resp)

    env = {"OLOSTEP_API_KEY": "test-key", "PAGE_CACHE_DIR": str(tmp_path)}
    with patch("app.providers.httpx.AsyncClient", return_value=mock_client), \
         patch("app.providers.os.environ", env):
        first = await fetch_page("https://scholarships.gov.in/scheme")
        second = await fetch_page("https://scholarships.gov.in/scheme")

    assert first == "# Cached scheme"
    assert second == "# Cached scheme"
    mock_client.post.assert_called_once()
    assert len(list(tmp_path.glob("*.md"))) == 1


@pytest.mark.asyncio
async def test_fetch_page_bypass_cache_arg_and_env(tmp_path):
    """bypass_cache=True or BYPASS_PAGE_CACHE=1 skips reading cache."""
    scrape_resp_1 = _make_scrape_response({"markdown_content": "v1"})
    scrape_resp_2 = _make_scrape_response({"markdown_content": "v2"})
    scrape_resp_3 = _make_scrape_response({"markdown_content": "v3"})

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post = AsyncMock(side_effect=[scrape_resp_1, scrape_resp_2, scrape_resp_3])

    env = {"OLOSTEP_API_KEY": "test-key", "PAGE_CACHE_DIR": str(tmp_path)}
    with patch("app.providers.httpx.AsyncClient", return_value=mock_client), \
         patch("app.providers.os.environ", env):
        assert await fetch_page("https://scholarships.gov.in/s") == "v1"
        assert await fetch_page("https://scholarships.gov.in/s", bypass_cache=True) == "v2"
        env["BYPASS_PAGE_CACHE"] = "1"
        assert await fetch_page("https://scholarships.gov.in/s") == "v3"
        env.pop("BYPASS_PAGE_CACHE")
        assert await fetch_page("https://scholarships.gov.in/s") == "v3"

    assert mock_client.post.call_count == 3
