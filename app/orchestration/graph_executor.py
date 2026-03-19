"""Graph-mode executor for DAG nodes with parallel group scheduling."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

from app.schemas.api import ExecutionTraceRecord, SkillSelection, TaskGraphSpec, TaskNodeSpec


@dataclass
class NodeRunResult:
    trace: ExecutionTraceRecord
    skill_selection: SkillSelection
    output: dict[str, object]


class GraphExecutor:
    def __init__(self, max_workers: int = 4) -> None:
        self._max_workers = max_workers

    def run(
        self,
        graph: TaskGraphSpec,
        execute_node: Callable[[TaskNodeSpec, dict[str, dict[str, object]]], NodeRunResult],
    ) -> tuple[list[ExecutionTraceRecord], list[SkillSelection], dict[str, dict[str, object]], str | None]:
        nodes_by_id = {node.node_id: node for node in graph.nodes}
        traces: list[ExecutionTraceRecord] = []
        skills: list[SkillSelection] = []
        outputs: dict[str, dict[str, object]] = {}
        failed_node: str | None = None

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            for group in graph.parallel_groups:
                futures = {}
                for node_id in group:
                    node = nodes_by_id.get(node_id)
                    if node is None:
                        continue
                    if any(dep not in outputs for dep in node.depends_on):
                        trace = ExecutionTraceRecord(
                            node_id=node.node_id,
                            status="skipped",
                            error="dependencies_not_satisfied",
                            result={},
                        )
                        traces.append(trace)
                        continue
                    dependency_outputs = {dep: outputs[dep] for dep in node.depends_on}
                    future = pool.submit(execute_node, node, dependency_outputs)
                    futures[future] = node

                for future in as_completed(futures):
                    node = futures[future]
                    result = future.result()
                    traces.append(result.trace)
                    skills.append(result.skill_selection)
                    outputs[node.node_id] = result.output
                    if result.trace.status == "failed" and failed_node is None:
                        failed_node = node.node_id

                if failed_node is not None:
                    break

        return traces, skills, outputs, failed_node
