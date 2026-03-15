from __future__ import annotations

from pathlib import Path

from app.models.router import ModelRouter


def test_model_router_routes_by_task_and_sensitivity(tmp_path: Path) -> None:
    cfg = tmp_path / "routing.yaml"
    cfg.write_text(
        "\n".join(
            [
                "default_provider: cloud",
                "providers:",
                "  local:",
                "    model: local-x",
                "    timeout_seconds: 10",
                "    max_tokens: 256",
                "  cloud:",
                "    model: cloud-y",
                "    timeout_seconds: 20",
                "    max_tokens: 512",
                "rules:",
                "  - task_type: automation",
                "    sensitivity: high",
                "    provider: local",
                "fallback_order:",
                "  - cloud",
            ]
        ),
        encoding="utf-8",
    )

    router = ModelRouter.from_file(cfg)
    routed = router.route(task_type="automation", sensitivity="high")
    assert routed.provider == "local"
    assert routed.config.name == "local-x"

    routed_default = router.route(task_type="qa", sensitivity="low")
    assert routed_default.provider == "cloud"

