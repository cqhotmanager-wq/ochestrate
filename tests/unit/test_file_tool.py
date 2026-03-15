from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from docx import Document

from app.tools.file_tool import FileTool
from app.tools.security import ToolSecurityConfig


@pytest.fixture
def file_tool(tmp_path: Path) -> FileTool:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    security = ToolSecurityConfig(
        allowed_directories=[data_dir.resolve()],
        allowed_domains=["*"],
        fetch_timeout_seconds=10,
        max_fetch_chars=1000,
        search_provider="duckduckgo",
        search_result_limit=5,
        db_write_protection_enabled=True,
        db_confirm_field="confirm_write",
        max_file_size_mb=2,
    )
    return FileTool(security=security, workspace=tmp_path)


def test_file_tool_read_write_json(file_tool: FileTool, tmp_path: Path) -> None:
    target = "data/sample.json"
    payload = {"a": 1, "b": "x"}
    file_tool.run({"operation": "write", "resource_path": target, "content": payload})
    result = file_tool.run({"operation": "read", "resource_path": target})
    assert result["data"] == payload


def test_file_tool_read_docx(file_tool: FileTool, tmp_path: Path) -> None:
    path = tmp_path / "data" / "sample.docx"
    doc = Document()
    doc.add_paragraph("hello world")
    doc.save(path)
    result = file_tool.run({"operation": "read", "resource_path": "data/sample.docx"})
    assert "hello world" in result["text"]


def test_file_tool_read_excel(file_tool: FileTool, tmp_path: Path) -> None:
    path = tmp_path / "data" / "sample.xlsx"
    pd.DataFrame([{"name": "alice"}, {"name": "bob"}]).to_excel(path, index=False)
    result = file_tool.run({"operation": "read", "resource_path": "data/sample.xlsx"})
    assert len(result["rows"]) == 2


def test_file_tool_rejects_outside_allowed_directory(file_tool: FileTool) -> None:
    with pytest.raises(PermissionError):
        file_tool.run({"operation": "read", "resource_path": "../forbidden.txt"})

