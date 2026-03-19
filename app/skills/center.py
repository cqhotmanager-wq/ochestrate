"""技能中心：处理技能模板持久化、缓存与版本选择。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas.specs import SkillSpec


class SkillCenter:
    def __init__(self, storage_dir: Path) -> None:
        # 步骤：执行 `__init__` 的核心处理逻辑。
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, SkillSpec] = {}

    @property
    def storage_dir(self) -> Path:
        # 步骤：执行 `storage_dir` 的核心处理逻辑。
        return self._storage_dir

    def generate_skill(
        self,
        skill_id: str,
        name: str,
        prompt_template: str,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> SkillSpec:
        # 步骤：执行 `generate_skill` 的核心处理逻辑。
        skill = SkillSpec(
            skill_id=skill_id,
            version=version,
            name=name,
            prompt_template=prompt_template,
            config=config or {},
        )
        self.save_skill(skill)
        return skill

    def save_skill(self, skill: SkillSpec) -> None:
        # 步骤：执行 `save_skill` 的核心处理逻辑。
        target = self._storage_dir / f"{skill.skill_id}_{skill.version}.json"
        target.write_text(skill.model_dump_json(indent=2), encoding="utf-8")
        self._cache[self._key(skill.skill_id, skill.version)] = skill

    def load_skill(self, skill_id: str, version: str) -> SkillSpec:
        # 步骤：执行 `load_skill` 的核心处理逻辑。
        key = self._key(skill_id, version)
        if key in self._cache:
            return self._cache[key]
        target = self._storage_dir / f"{skill_id}_{version}.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        skill = SkillSpec(**payload)
        self._cache[key] = skill
        return skill

    def latest_skill(self, skill_id: str) -> SkillSpec | None:
        # 步骤：执行 `latest_skill` 的核心处理逻辑。
        candidates = sorted(self._storage_dir.glob(f"{skill_id}_*.json"))
        if not candidates:
            return None
        payload = json.loads(candidates[-1].read_text(encoding="utf-8"))
        return SkillSpec(**payload)

    def list_latest_skills(self) -> list[SkillSpec]:
        # 步骤：执行 `list_latest_skills` 的核心处理逻辑。
        by_skill_id: dict[str, SkillSpec] = {}
        for file in sorted(self._storage_dir.glob("*.json")):
            payload = json.loads(file.read_text(encoding="utf-8"))
            spec = SkillSpec(**payload)
            existing = by_skill_id.get(spec.skill_id)
            if existing is None or self._version_gt(spec.version, existing.version):
                by_skill_id[spec.skill_id] = spec
        return sorted(by_skill_id.values(), key=lambda x: x.skill_id)

    @staticmethod
    def _key(skill_id: str, version: str) -> str:
        # 步骤：执行 `_key` 的核心处理逻辑。
        return f"{skill_id}:{version}"

    @staticmethod
    def _version_gt(new: str, old: str) -> bool:
        # 步骤：执行 `_version_gt` 的核心处理逻辑。
        try:
            return [int(x) for x in new.split(".")] > [int(x) for x in old.split(".")]
        except ValueError:
            return new > old



