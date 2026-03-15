from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.skills.center import SkillCenter


@dataclass
class SkillContextItem:
    name: str
    description: str
    skill_path: str
    version: str | None = None
    explicit_enabled: bool = False


class SkillContextService:
    def __init__(self, skill_center: SkillCenter, scan_dirs: list[Path], skill_scan_glob: str) -> None:
        self._center = skill_center
        self._scan_dirs = scan_dirs
        self._scan_glob = skill_scan_glob

    def load(self) -> list[SkillContextItem]:
        from_center = self._load_from_skill_center()
        from_files = self._load_from_skill_md()
        merged: dict[str, SkillContextItem] = {}

        for item in from_files:
            merged[item.name.lower()] = item
        for item in from_center:
            key = item.name.lower()
            existing = merged.get(key)
            if existing is None:
                merged[key] = item
                continue
            if item.explicit_enabled and not existing.explicit_enabled:
                merged[key] = item
                continue
            if self._version_gt(item.version, existing.version):
                merged[key] = item

        return sorted(merged.values(), key=lambda x: x.name.lower())

    def _load_from_skill_center(self) -> list[SkillContextItem]:
        items: list[SkillContextItem] = []
        for skill in self._center.list_latest_skills():
            description = (skill.prompt_template or "").strip().replace("\n", " ")
            if len(description) > 180:
                description = description[:180] + "..."
            items.append(
                SkillContextItem(
                    name=skill.name,
                    description=description or "Skill generated from SkillCenter.",
                    skill_path=str((self._center.storage_dir / f"{skill.skill_id}_{skill.version}.json").resolve()),
                    version=skill.version,
                    explicit_enabled=True,
                )
            )
        return items

    def _load_from_skill_md(self) -> list[SkillContextItem]:
        items: list[SkillContextItem] = []
        for root in self._scan_dirs:
            if not root.exists():
                continue
            for skill_file in root.glob(self._scan_glob):
                if not skill_file.is_file():
                    continue
                text = skill_file.read_text(encoding="utf-8", errors="ignore")
                name = self._extract_name(skill_file, text)
                description = self._extract_description(text)
                items.append(
                    SkillContextItem(
                        name=name,
                        description=description,
                        skill_path=str(skill_file.resolve()),
                    )
                )
        return items

    @staticmethod
    def _extract_name(path: Path, text: str) -> str:
        for line in text.splitlines():
            clean = line.strip()
            if clean.startswith("#"):
                return clean.lstrip("#").strip() or path.parent.name
        return path.parent.name

    @staticmethod
    def _extract_description(text: str) -> str:
        for line in text.splitlines():
            clean = line.strip()
            if clean and not clean.startswith("#"):
                clean = re.sub(r"\s+", " ", clean)
                return clean[:180] + ("..." if len(clean) > 180 else "")
        return "Skill loaded from SKILL.md."

    @staticmethod
    def _version_gt(new: str | None, old: str | None) -> bool:
        if not new:
            return False
        if not old:
            return True
        try:
            new_parts = [int(x) for x in new.split(".")]
            old_parts = [int(x) for x in old.split(".")]
            return new_parts > old_parts
        except ValueError:
            return new > old

