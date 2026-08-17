"""Live web search tool — requests + BeautifulSoup, no external search API.

search(query) → fetches a real search results page → follows the top result →
extracts text. Typed errors only: fetch_failed / timeout / invalid_query.
The tool enforces its own timeout with a worker thread (real enforcement even
for injected transports that ignore the requests timeout kwarg).
"""

import base64
import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup
import requests

from agent.core.types import ToolResult
from agent.tools import BaseTool

SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
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

    def _result_urls(self, query: str, limit: int = 5) -> list[tuple[str, str]]:
        """Return (url, title) pairs for the top organic results, trying
        DuckDuckGo first and falling back to Bing when DDG rate-limits
        (HTTP 202 anomaly page) or returns no organic results."""
        ddg = self._ddg_results(query, limit)
        if ddg:
            return ddg
        return self._bing_results(query, limit)

    def _ddg_results(self, query: str, limit: int = 5) -> list[tuple[str, str]]:
        resp = self._get(SEARCH_ENDPOINT, params={"q": query})
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[tuple[str, str]] = []
        for a in soup.select("a.result__a"):
            title = a.get_text(" ", strip=True)
            href = a.get("href", "")
            url = self._decode_ddg_redirect(href)
            if not url:
                continue
            results.append((url, title))
            if len(results) >= limit:
                break
        return results

    def _bing_results(self, query: str, limit: int = 5) -> list[tuple[str, str]]:
        resp = self._get("https://www.bing.com/search", params={"q": query})
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[tuple[str, str]] = []
        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a") or li.select_one("a")
            if not a:
                continue
            title = a.get_text(" ", strip=True)
            href = a.get("href", "")
            if href.startswith("http") and "bing.com/ck/a" not in href:
                url = href
            else:
                url = self._decode_bing_redirect(href)
            if not url:
                continue
            results.append((url, title))
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _decode_ddg_redirect(href: str) -> str:
        """DuckDuckGo wraps results in /l/?uddg=<urlencoded> redirects."""
        if "uddg=" not in href:
            return href if href.startswith("http") else ""
        q = parse_qs(urlparse(href).query)
        target = q.get("uddg", [""])[0]
        if not target:
            return ""
        return unquote(target)

    @staticmethod
    def _decode_bing_redirect(href: str) -> str:
        """Legacy Bing /ck/a redirect decoder (kept for compatibility)."""
        if "bing.com/ck/a" not in href:
            return ""
        encoded = parse_qs(urlparse(href).query).get("u", [""])[0]
        if not encoded:
            return ""

        def _try(raw: str) -> str:
            padded = raw + "=" * (-len(raw) % 4)
            try:
                return base64.urlsafe_b64decode(padded).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                return ""

        decoded = _try(encoded)
        if decoded.startswith("http"):
            return decoded
        for offset in range(1, 4):
            decoded = _try(encoded[offset:])
            if decoded.startswith("http"):
                return decoded
        return ""

    @staticmethod
    def _relevance(url: str, title: str, query: str) -> int:
        """Score a result by how many distinctive query tokens appear in its
        title/url, so a Python-focused query prefers a Python page over a
        generic one. Weak tokens (best, top, web, etc.) match too broadly."""
        stopwords = {
            "best", "top", "web", "open", "source", "task", "project",
            "research", "how", "what", "about", "using", "with", "for",
            "the", "and", "free",
        }
        tokens = [
            t for t in query.lower().split()
            if len(t) > 2 and t not in stopwords
        ]
        if not tokens:
            return 0
        hay = f"{title.lower()} {url.lower()}"
        return sum(1 for t in tokens if t in hay)

    def _is_safe_url(self, url: str) -> bool:
        """Blocks non-http(s) schemes and private/loopback/metadata hosts (SSRF)."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname or ""
        if host in ("localhost", "127.0.0.1", "::1"):
            return False
        if host == "169.254.169.254":  # cloud metadata
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            # hostname: resolve and re-check
            try:
                for info in socket.getaddrinfo(host, parsed.port or 80):
                    addr = ipaddress.ip_address(info[4][0])
                    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                        return False
                return True
            except (socket.gaierror, ValueError):
                return False
        return True

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
                if not self._is_safe_url(url):
                    return ToolResult.failure("unsafe_url")
                target = url
                content = self._bounded(self._extract_content, target)
            else:
                target = ""
                content = ""
                results = self._bounded(self._result_urls, query)
                results.sort(
                    key=lambda r: self._relevance(r[0], r[1], query),
                    reverse=True,
                )
                for candidate, _title in results:
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