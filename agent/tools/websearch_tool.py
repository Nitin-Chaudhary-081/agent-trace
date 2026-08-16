"""Live web search tool — requests + BeautifulSoup, no external search API.

search(query) → fetches a real search results page → follows the top result →
extracts text. Typed errors only: fetch_failed / timeout / invalid_query.
The tool enforces its own timeout with a worker thread (real enforcement even
for injected transports that ignore the requests timeout kwarg).
"""

import base64
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup
import requests

from agent.core.types import ToolResult
from agent.tools import BaseTool

SEARCH_ENDPOINT = "https://www.bing.com/search"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class WebSearchTool(BaseTool):
    name: str = "web_search"
    timeout_s: float = 60.0
    max_content_chars: int = 8000
    session: Any = field(default=None, repr=False)

    def _get(self, url: str, **kwargs) -> requests.Response:
        session = self.session or requests.Session()
        kwargs.setdefault("headers", {"User-Agent": USER_AGENT})
        kwargs.setdefault("timeout", self.timeout_s)
        return session.get(url, **kwargs)

    def _bounded(self, fn, *args, **kwargs) -> Any:
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(fn, *args, **kwargs)
            return future.result(timeout=self.timeout_s)
        finally:
            future.cancel()
            pool.shutdown(wait=False)

    def _result_urls(self, query: str, limit: int = 5) -> list[str]:
        resp = self._get(SEARCH_ENDPOINT, params={"q": query})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        urls: list[str] = []
        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a") or li.select_one("a")
            if not a:
                continue
            href = a.get("href", "")
            if href.startswith("http") and "bing.com/ck/a" not in href:
                urls.append(href)
                continue
            decoded = self._decode_bing_redirect(href)
            if decoded:
                urls.append(decoded)
            if len(urls) >= limit:
                break
        return urls

    @staticmethod
    def _decode_bing_redirect(href: str) -> str:
        """Bing wraps organic results in /ck/a redirects; the real URL is the
        base64-encoded `u` query parameter (which may carry a junk prefix).
        """
        from urllib.parse import parse_qs, urlparse

        if "bing.com/ck/a" not in href:
            return ""
        encoded = parse_qs(urlparse(href).query).get("u", [""])[0]
        if not encoded:
            return ""

        def _try(raw: str) -> str:
            padded = raw + "=" * (-len(raw) % 4)
            try:
                return base64.urlsafe_b64decode(padded).decode("utf-8")
            except (ValueError, UnicodeDecodeError, Exception):  # noqa: BLE001
                return ""

        decoded = _try(encoded)
        if decoded.startswith("http"):
            return decoded
        for offset in range(1, 4):
            decoded = _try(encoded[offset:])
            if decoded.startswith("http"):
                return decoded
        return ""

    def _extract_content(self, url: str) -> str:
        resp = self._get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return text[: self.max_content_chars]

    def invoke(self, query: str = "", url: str = "", **params: Any) -> ToolResult:
        if not query.strip():
            return ToolResult.failure("invalid_query")
        try:
            if url:
                target = url
                content = self._bounded(self._extract_content, target)
            else:
                target = ""
                content = ""
                for candidate in self._bounded(self._result_urls, query):
                    try:
                        content = self._bounded(self._extract_content, candidate)
                        target = candidate
                        break
                    except Exception:  # noqa: BLE001 - try next result
                        continue
        except TimeoutError:
            return ToolResult.failure("timeout")
        except Exception:  # noqa: BLE001 - transport boundary: map to typed error
            return ToolResult.failure("fetch_failed")
        if not content or not target:
            return ToolResult.failure("fetch_failed")
        return ToolResult(
            success=True,
            output={"url": target, "content": content},
            error=None,
            duration_ms=0,
        )