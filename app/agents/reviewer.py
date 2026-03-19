"""Reflection and verification engine."""

from __future__ import annotations

from app.schemas.api import ExecutionTraceRecord, ReflectionRecord, TaskGraphSpec, VerificationReport


class ReflectionEngine:
    def reflect(
        self,
        node_id: str,
        result: dict[str, object],
        error: str | None,
        retry_count: int,
    ) -> ReflectionRecord:
        if error:
            if retry_count < 1:
                return ReflectionRecord(
                    node_id=node_id,
                    decision="retry",
                    reason=f"node execution error: {error}",
                    retry_count=retry_count,
                )
            return ReflectionRecord(
                node_id=node_id,
                decision="fail",
                reason=f"node failed after retry: {error}",
                retry_count=retry_count,
            )

        if not result:
            if retry_count < 1:
                return ReflectionRecord(
                    node_id=node_id,
                    decision="retry",
                    reason="empty result payload",
                    retry_count=retry_count,
                )
            return ReflectionRecord(
                node_id=node_id,
                decision="fail",
                reason="empty result after retry",
                retry_count=retry_count,
            )

        return ReflectionRecord(
            node_id=node_id,
            decision="accept",
            reason="result accepted",
            retry_count=retry_count,
        )

    def verify(self, graph: TaskGraphSpec, trace: list[ExecutionTraceRecord]) -> VerificationReport:
        trace_by_id = {item.node_id: item for item in trace}
        missing = [node.node_id for node in graph.nodes if node.node_id not in trace_by_id]
        failed = [item.node_id for item in trace if item.status == "failed"]

        checks = [
            f"nodes_total={len(graph.nodes)}",
            f"trace_total={len(trace)}",
            f"failed_nodes={len(failed)}",
        ]
        return VerificationReport(
            all_tasks_completed=not missing and not failed,
            outputs_consistent=not failed,
            missing_nodes=missing,
            checks=checks,
        )


class ReviewerAgent(ReflectionEngine):
    """Backward-compatible alias for previous wiring."""

