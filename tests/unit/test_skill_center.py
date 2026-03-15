from __future__ import annotations

from pathlib import Path

from app.skills.center import SkillCenter


def test_skill_generation_and_loading(tmp_path: Path) -> None:
    center = SkillCenter(storage_dir=tmp_path)
    created = center.generate_skill(
        skill_id="kb_qa",
        version="1.0.0",
        name="KB QA",
        prompt_template="Answer with citations.",
        config={"temperature": 0.1},
    )

    loaded = center.load_skill("kb_qa", "1.0.0")
    assert loaded.skill_id == created.skill_id
    assert loaded.prompt_template == "Answer with citations."

