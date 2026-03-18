"""技能接口：创建技能模板并按版本读取技能定义。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import require_auth_context
from app.auth.schemas import AuthContext
from app.core.dependencies import ServiceContainer, get_container
from app.schemas.api import CreateSkillRequest
from app.schemas.specs import SkillSpec

router = APIRouter(prefix="/skills", tags=["skills"])


@router.post("", response_model=SkillSpec)
def create_skill(
    payload: CreateSkillRequest,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> SkillSpec:
    _ = auth
    return container.skill_center.generate_skill(
        skill_id=payload.skill_id,
        version=payload.version,
        name=payload.name,
        prompt_template=payload.prompt_template,
        config=payload.config,
    )


@router.get("/{skill_id}/{version}", response_model=SkillSpec)
def get_skill(
    skill_id: str,
    version: str,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> SkillSpec:
    _ = auth
    try:
        return container.skill_center.load_skill(skill_id=skill_id, version=version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


