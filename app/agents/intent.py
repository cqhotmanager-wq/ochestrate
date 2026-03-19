"""Intent analyzer for goal/constraints/output extraction and clarification gating."""

from __future__ import annotations

import re

from app.schemas.api import IntentSummary, UnifiedRequest


class IntentAnalyzer:
    _CONSTRAINT_PATTERNS = [
        r"\bmust\b",
        r"\bshould\b",
        r"\bwithin\b",
        r"\bunder\b",
        r"\bat most\b",
        r"\bno more than\b",
        r"不能",
        r"不要",
        r"必须",
    ]

    _OUTPUT_HINTS = {
        "report": "structured report",
        "json": "json payload",
        "table": "tabular result",
        "list": "bullet list",
        "diagram": "diagram",
        "code": "code changes",
        "api": "api response",
    }

    _VAGUE_TOKENS = {"something", "anything", "stuff", "whatever", "optimize project"}

    def analyze(self, request: UnifiedRequest) -> IntentSummary:
        text = request.input.strip()
        goal = self._extract_goal(text)
        constraints = self._extract_constraints(text)
        expected_output = self._extract_expected_output(text)

        needs_clarification = self._needs_clarification(text=text, expected_output=expected_output, request=request)
        clarifications: list[str] = []
        if needs_clarification:
            clarifications = [
                "Please specify exact success criteria for the task.",
                "Please specify required output format (for example: report/json/list).",
            ]

        assumption_flags: list[str] = []
        if not constraints:
            assumption_flags.append("no_explicit_constraints")
        if not expected_output:
            assumption_flags.append("output_format_inferred")

        return IntentSummary(
            goal=goal,
            constraints=constraints,
            expected_output=expected_output,
            assumption_flags=assumption_flags,
            needs_clarification=needs_clarification,
            clarifications=clarifications,
        )

    @staticmethod
    def _extract_goal(text: str) -> str:
        sentence = re.split(r"[.!?。！？]", text)[0].strip()
        return sentence or text

    def _extract_constraints(self, text: str) -> list[str]:
        constraints: list[str] = []
        lower = text.lower()
        for pattern in self._CONSTRAINT_PATTERNS:
            if re.search(pattern, lower):
                constraints.append(f"contains constraint marker: {pattern}")
        if "budget" in lower or "cost" in lower:
            constraints.append("budget constrained")
        if "deadline" in lower or "before" in lower:
            constraints.append("time constrained")
        return constraints

    def _extract_expected_output(self, text: str) -> list[str]:
        lower = text.lower()
        outputs = [label for token, label in self._OUTPUT_HINTS.items() if token in lower]
        return sorted(set(outputs))

    def _needs_clarification(self, text: str, expected_output: list[str], request: UnifiedRequest) -> bool:
        lowered = text.lower()
        if request.tool_payload is not None:
            return False
        if len(lowered.split()) < 3 and len(text) < 12:
            return True
        if any(token in lowered for token in self._VAGUE_TOKENS) and not expected_output:
            return True
        return False
