# 文件说明：LangGraph 节点：evidence_verify。
from typing import Literal

from app.evidence.models import EvidenceRecord
from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.schemas.ai import ItineraryDraftContract, ValidationIssueContract
from app.services.evidence_validation_service import EvidenceValidationService
from app.skills.executor import SkillContext
from app.skills.production import EvidenceVerificationOutput
from app.skills.runtime import SkillRuntime


async def evidence_verify_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
    skill_runtime: SkillRuntime | None = None,
) -> dict[str, object]:
    if state.get("status") != "completed" or state.get("draft") is None:
        return {"events": graph_runtime.event_dicts()}
    graph_runtime.emit(
        "stage",
        stage="evidence_verify",
        message="正在核验行程事实与 Evidence",
    )
    draft = ItineraryDraftContract.model_validate(state["draft"])
    records = [
        EvidenceRecord.model_validate(item)
        for item in state.get("evidence_records", [])
    ]
    report = EvidenceValidationService().validate(draft, records=records)
    skills_used = [dict(item) for item in state.get("skills_used", [])]
    skill_validation_issues: list[ValidationIssueContract] = []
    evidence_manifest = (
        None
        if skill_runtime is None
        else skill_runtime.selected_manifests.get("evidence-verification")
    )
    if skill_runtime is not None and evidence_manifest is not None:
        try:
            handler = skill_runtime.handlers.get("evidence-verification")
            if handler is None:
                raise LookupError("evidence-verification handler missing")
            evidence_result = await skill_runtime.executor.execute(
                evidence_manifest,
                SkillContext(
                    tool_registry=skill_runtime.tools,
                    tool_context=skill_runtime.tool_context,
                    handler=handler,
                ),
                {
                    "records": [
                        record.model_dump(mode="json")
                        for record in records
                    ],
                },
            )
            skills_used.append(
                {
                    "name": evidence_result.skill_name,
                    "version": evidence_result.version,
                    "status": evidence_result.status,
                }
            )
            verification = EvidenceVerificationOutput.model_validate(
                evidence_result.output
            )
            skill_validation_issues.extend(
                ValidationIssueContract(
                    code=_verification_issue_code(issue.code),
                    severity="warning",
                    path=issue.path,
                    message=issue.message,
                )
                for issue in verification.issues
            )
        except Exception as exc:
            graph_runtime.emit(
                "validation",
                stage="evidence_skill",
                status="warning",
                message="Evidence Verification Skill 执行失败，保留规则校验结果",
                payload={"error": type(exc).__name__},
            )
    validation_issues = _deduplicate_issues(
        [
            *report.as_validation_issues(),
            *skill_validation_issues,
        ]
    )
    merged_issues = [
        *draft.validation_summary,
        *validation_issues,
    ]
    updated_draft = draft.model_copy(
        update={"validation_summary": merged_issues}
    )
    has_blocking_issue = any(
        issue.severity in {"error", "fatal"}
        for issue in validation_issues
    )
    graph_runtime.emit(
        "validation",
        stage="evidence_verify",
        status="warning" if validation_issues else "passed",
        message=(
            f"Evidence 核验发现 {len(validation_issues)} 个问题"
            if validation_issues
            else "Evidence 核验通过"
        ),
        payload={
            "verified_count": report.verified_count,
            "issue_codes": [issue.code for issue in report.issues],
        },
    )
    return {
        "status": "partial" if has_blocking_issue else "completed",
        "draft": updated_draft.model_dump(mode="json"),
        "issues": [
            issue.model_dump(mode="json")
            for issue in validation_issues
        ],
        "evidence_issues": [
            issue.model_dump(mode="json")
            for issue in report.issues
        ],
        "skills_used": skills_used,
        "events": graph_runtime.event_dicts(),
    }


def _deduplicate_issues(
    issues: list[ValidationIssueContract],
) -> list[ValidationIssueContract]:
    unique = {
        (issue.code, issue.path, issue.message): issue
        for issue in issues
    }
    return list(unique.values())


def _verification_issue_code(
    code: str,
) -> Literal[
    "evidence_missing",
    "evidence_stale",
    "evidence_conflict",
    "unsupported_claim",
    "invalid_schema",
]:
    mapping: dict[
        str,
        Literal[
            "evidence_missing",
            "evidence_stale",
            "evidence_conflict",
            "unsupported_claim",
            "invalid_schema",
        ],
    ] = {
        "missing": "evidence_missing",
        "stale": "evidence_stale",
        "conflict": "evidence_conflict",
        "unsupported_claim": "unsupported_claim",
    }
    return mapping.get(code, "invalid_schema")
