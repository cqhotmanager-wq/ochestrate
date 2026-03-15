from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.tools.security import ToolSecurityConfig
from app.tools.web_tools import WebFetchTool, WebSearchTool


@dataclass
class DummyResponse:
    text: str
    status_code: int = 200
    headers: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = {"content-type": "text/html; charset=utf-8"}


@pytest.fixture
def security() -> ToolSecurityConfig:
    return ToolSecurityConfig(
        allowed_directories=[],
        allowed_domains=["example.com", "duckduckgo.com"],
        fetch_timeout_seconds=10,
        max_fetch_chars=500,
        search_provider="duckduckgo",
        search_result_limit=3,
        db_write_protection_enabled=True,
        db_confirm_field="confirm_write",
        max_file_size_mb=2,
    )


def test_web_fetch_tool_success(monkeypatch: pytest.MonkeyPatch, security: ToolSecurityConfig) -> None:
    def fake_get(url: str, timeout: int):
        return DummyResponse("<html><title>T</title><body>Hello</body></html>")

    monkeypatch.setattr("app.tools.web_tools.requests.get", fake_get)
    tool = WebFetchTool(security=security)
    result = tool.run({"url": "https://example.com/page"})
    assert result["status_code"] == 200
    assert "Hello" in result["text"]


def test_web_search_tool(monkeypatch: pytest.MonkeyPatch, security: ToolSecurityConfig) -> None:
    search_html = """
    <html><body>
      <div class="result">
        <a class="result__a" href="https://example.com/a">Result A</a>
        <div class="result__snippet">Snippet A</div>
      </div>
    </body></html>
    """

    def fake_get(url: str, timeout: int):
        if "duckduckgo.com" in url:
            return DummyResponse(search_html)
        return DummyResponse("<html><body>Fetched A</body></html>")

    monkeypatch.setattr("app.tools.web_tools.requests.get", fake_get)
    fetch_tool = WebFetchTool(security=security)
    search_tool = WebSearchTool(security=security, fetch_tool=fetch_tool)
    result = search_tool.run({"query": "test", "include_fetch": True})
    assert result["results"]
    assert result["results"][0]["title"] == "Result A"

