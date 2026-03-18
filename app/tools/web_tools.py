"""网络工具：提供网页抓取与搜索并执行 SSRF 防护。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.tools.security import ToolSecurityConfig


class WebFetchTool:
    name = "web_fetch_tool"
    description = "Fetch URL content with domain allow-list and content-type controls."
    required_roles = ["employee", "manager", "admin"]
    idempotent = True

    def __init__(self, security: ToolSecurityConfig) -> None:
        self._security = security

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """抓取单个 URL 内容并执行安全过滤。"""
        url = str(params.get("url") or "").strip()
        if not url:
            raise ValueError("url is required")
        if not self._security.is_url_safe(url):
            raise PermissionError(f"domain is not allowed for url '{url}'")
        response = self._safe_get(url)
        content_type = response.headers.get("content-type", "").lower()
        body = response.text
        title = ""
        if "html" in content_type:
            soup = BeautifulSoup(body, "html.parser")
            title = (soup.title.string or "").strip() if soup.title else ""
            body = soup.get_text(separator="\n", strip=True)
        elif "json" in content_type:
            body = response.text
        elif "text" not in content_type:
            raise ValueError(f"unsupported content type '{content_type}'")

        trimmed = body[: self._security.max_fetch_chars]
        return {
            "url": getattr(response, "url", url),
            "status_code": response.status_code,
            "content_type": content_type,
            "title": title,
            "text": trimmed,
        }

    def _safe_get(self, url: str) -> requests.Response:
        """
        手动重定向控制，确保每次跳转都经过域名/协议/私网校验，避免 SSRF。
        """
        current = url
        with requests.Session() as session:
            for _ in range(self._security.max_redirects + 1):
                # 禁用 requests 自动跳转，改为逐跳手工校验。
                resp = session.get(
                    current,
                    timeout=self._security.fetch_timeout_seconds,
                    allow_redirects=False,
                    stream=True,
                )
                location = resp.headers.get("location")
                if location and resp.is_redirect:
                    next_url = urljoin(current, location)
                    if not self._security.is_url_safe(next_url):
                        raise PermissionError(f"redirect target is not allowed: '{next_url}'")
                    current = next_url
                    continue

                # 落地内容前先校验响应头，避免下载异常大文件或二进制流。
                self._validate_content_headers(resp)
                text = resp.text
                if len(text) > self._security.max_fetch_chars:
                    resp._content = text[: self._security.max_fetch_chars].encode(resp.encoding or "utf-8")
                return resp
        raise ValueError("too many redirects")

    def _validate_content_headers(self, response: requests.Response) -> None:
        content_type = (response.headers.get("content-type") or "").lower()
        if not any(x in content_type for x in ("text", "json", "xml", "html", "markdown")):
            raise ValueError(f"unsupported content type '{content_type}'")
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > self._security.max_fetch_chars * 4:
            raise ValueError("response body is too large")


class WebSearchTool:
    name = "web_search_tool"
    description = "Search web by keyword and optionally fetch top result contents."
    required_roles = ["employee", "manager", "admin"]
    idempotent = True

    def __init__(self, security: ToolSecurityConfig, fetch_tool: WebFetchTool) -> None:
        self._security = security
        self._fetch_tool = fetch_tool

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """执行关键词搜索，并可选抓取结果页摘要。"""
        query = str(params.get("query") or params.get("q") or "").strip()
        if not query:
            raise ValueError("query is required")
        max_results = int(params.get("max_results", self._security.search_result_limit))
        include_fetch = bool(params.get("include_fetch", True))

        if self._security.search_provider.lower() != "duckduckgo":
            raise ValueError(f"unsupported search provider '{self._security.search_provider}'")

        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        resp = requests.get(url, timeout=self._security.fetch_timeout_seconds)
        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[dict[str, Any]] = []
        for result in soup.select(".result"):
            anchor = result.select_one(".result__a")
            if anchor is None:
                continue
            href = self._normalize_result_url(anchor.get("href") or "")
            title = anchor.get_text(strip=True)
            snippet_el = result.select_one(".result__snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            item = {"title": title, "url": href, "snippet": snippet}
            if include_fetch and href and self._security.is_url_safe(href):
                try:
                    # 对命中的结果再做二次抓取，返回更长的可读摘要。
                    fetched = self._fetch_tool.run({"url": href})
                    item["fetched_excerpt"] = fetched.get("text", "")
                except Exception as exc:
                    item["fetch_error"] = str(exc)
            results.append(item)
            if len(results) >= max_results:
                break

        return {"query": query, "provider": self._security.search_provider, "results": results}

    @staticmethod
    def _normalize_result_url(url: str) -> str:
        parsed = urlparse(url)
        if "duckduckgo.com" in (parsed.netloc or "") and parsed.path.startswith("/l/"):
            for part in (parsed.query or "").split("&"):
                if part.startswith("uddg="):
                    return unquote(part[len("uddg=") :])
        return url

