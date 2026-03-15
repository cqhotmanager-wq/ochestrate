from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

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
        url = str(params.get("url") or "").strip()
        if not url:
            raise ValueError("url is required")
        if not self._security.is_domain_allowed(url):
            raise PermissionError(f"domain is not allowed for url '{url}'")

        response = requests.get(url, timeout=self._security.fetch_timeout_seconds)
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
            "url": url,
            "status_code": response.status_code,
            "content_type": content_type,
            "title": title,
            "text": trimmed,
        }


class WebSearchTool:
    name = "web_search_tool"
    description = "Search web by keyword and optionally fetch top result contents."
    required_roles = ["employee", "manager", "admin"]
    idempotent = True

    def __init__(self, security: ToolSecurityConfig, fetch_tool: WebFetchTool) -> None:
        self._security = security
        self._fetch_tool = fetch_tool

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
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
            href = anchor.get("href") or ""
            title = anchor.get_text(strip=True)
            snippet_el = result.select_one(".result__snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            item = {"title": title, "url": href, "snippet": snippet}
            if include_fetch and href and self._security.is_domain_allowed(href):
                try:
                    fetched = self._fetch_tool.run({"url": href})
                    item["fetched_excerpt"] = fetched.get("text", "")
                except Exception as exc:
                    item["fetch_error"] = str(exc)
            results.append(item)
            if len(results) >= max_results:
                break

        return {"query": query, "provider": self._security.search_provider, "results": results}

