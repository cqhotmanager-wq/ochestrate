from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.compat.lang_runtime import get_prompt_template_cls
from app.context.token_budget import TokenBudgetManager
from app.skills.context import SkillContextItem


@dataclass
class PromptAssemblyInput:
    system_policy: str
    task: str
    evidence: str
    short_memory: str
    long_memory: str
    tools: list[dict[str, Any]]
    skills: list[SkillContextItem]
    max_skill_items: int
    skill_context_mode: str = "auto"


class PromptAssemblyService:
    def __init__(self, max_tokens: int) -> None:
        self._budget = TokenBudgetManager(max_tokens=max_tokens)
        template_cls = get_prompt_template_cls()
        self._template = (
            template_cls.from_template(
                "[SYSTEM_POLICY]\n{system_policy}\n\n"
                "[AVAILABLE_SKILLS]\n{skills}\n\n"
                "[AVAILABLE_TOOLS]\n{tools}\n\n"
                "[TASK]\n{task}\n\n"
                "[EVIDENCE]\n{evidence}\n\n"
                "[SHORT_MEMORY]\n{short_memory}\n\n"
                "[LONG_MEMORY]\n{long_memory}\n"
            )
            if template_cls is not None
            else None
        )

    def assemble(self, data: PromptAssemblyInput) -> str:
        skills_text = self._skills_section(data.skills, data.max_skill_items, data.skill_context_mode)
        tools_text = self._tools_section(data.tools)
        rendered = self._render_template(
            system_policy=data.system_policy,
            skills=skills_text,
            tools=tools_text,
            task=data.task,
            evidence=data.evidence,
            short_memory=data.short_memory,
            long_memory=data.long_memory,
        )
        tokens = self._budget.estimate_tokens(rendered)
        if tokens <= self._budget.max_tokens:
            return rendered
        return self._budget.truncate(rendered, self._budget.max_tokens)

    def _skills_section(
        self,
        skills: list[SkillContextItem],
        max_skill_items: int,
        skill_context_mode: str,
    ) -> str:
        if not skills:
            return "- none"

        selected = skills if skill_context_mode == "force_all" else skills[:max_skill_items]
        lines = []
        for item in selected:
            description = item.description.strip()
            if self._budget.estimate_tokens(description) > 40:
                description = self._budget.truncate(description, 40)
            lines.append(
                f"- name: {item.name}; description: {description}; skill_path: {item.skill_path}"
            )
        return "\n".join(lines)

    @staticmethod
    def _tools_section(tools: list[dict[str, Any]]) -> str:
        if not tools:
            return "- none"
        lines = []
        for tool in tools:
            lines.append(
                f"- {tool.get('name')}: {tool.get('description', '')}; "
                f"required_roles={tool.get('required_roles', [])}"
            )
        return "\n".join(lines)

    def _render_template(self, **kwargs: Any) -> str:
        if self._template is not None:
            return self._template.format(**kwargs)
        sections = [f"[{k.upper()}]\n{v}" for k, v in kwargs.items()]
        return "\n\n".join(sections)

