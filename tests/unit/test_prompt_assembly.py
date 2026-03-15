from __future__ import annotations

from pathlib import Path

from app.prompts.assembly import PromptAssemblyInput, PromptAssemblyService
from app.skills.center import SkillCenter
from app.skills.context import SkillContextService


def test_prompt_assembly_contains_skills_and_tools(tmp_path: Path) -> None:
    center = SkillCenter(storage_dir=tmp_path / "skills")
    center.generate_skill(
        skill_id="kb_qa",
        version="1.0.0",
        name="KB QA",
        prompt_template="Answer with citations in enterprise context.",
        config={},
    )
    skill_dir = tmp_path / "skill-md" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Demo Skill\nHelp with doc parsing.", encoding="utf-8")

    context_service = SkillContextService(
        skill_center=center,
        scan_dirs=[tmp_path / "skill-md"],
        skill_scan_glob="**/SKILL.md",
    )
    skills = context_service.load()
    assert len(skills) >= 2

    assembly = PromptAssemblyService(max_tokens=4096)
    prompt = assembly.assemble(
        PromptAssemblyInput(
            system_policy="Policy",
            task="Task content",
            evidence="Evidence content",
            short_memory="short",
            long_memory="long",
            tools=[{"name": "file_tool", "description": "file ops", "required_roles": ["employee"]}],
            skills=skills,
            max_skill_items=100,
            skill_context_mode="auto",
        )
    )
    assert "AVAILABLE_SKILLS" in prompt
    assert "skill_path" in prompt
    assert "file_tool" in prompt

