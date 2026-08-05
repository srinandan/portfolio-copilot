from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.contracts.ips import RelatedIPSVersion
from orchestrator.contracts.proposed_action import (
    ActionStatus,
    ActionType,
    OrderType,
    ProposedAction,
    Side,
    SkillVersionRef,
)
from orchestrator.contracts.reviewer_verdict import ReviewerVerdict, RuleResult
from orchestrator.executors.alpaca import AlpacaExecutionError, ExecutionResult
from orchestrator.gates.execution import execution_gate


@pytest.fixture
def sample_proposed_action():
    return ProposedAction(
        action_id="act-exec-101",
        session_id="sess-exec-1",
        type=ActionType.TRADE,
        ticker="GOOG",
        side=Side.BUY,
        quantity=10.0,
        order_type=OrderType.MARKET,
        estimated_price_usd=170.0,
        estimated_value_usd=1700.0,
        rationale="Rebalancing into equity per IPS target.",
        supporting_research_refs=[],
        ips_version_referenced=RelatedIPSVersion(ips_id="ips-1", version=1),
        proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version="0.2.0"),
        status=ActionStatus.DRAFTED,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_reviewer_verdict():
    return ReviewerVerdict(
        verdict_id="verdict-1",
        action_id="act-exec-101",
        ips_version_checked_against=RelatedIPSVersion(ips_id="ips-1", version=1),
        rule_results=[
            RuleResult(
                rule_id="concentration",
                description="Concentration limit check",
                passed=True,
                detail="OK",
            ),
        ],
        overall_pass=True,
        requires_human_approval=True,
        reviewer_skill_version=SkillVersionRef(
            skill_name="private-reviewer", skill_version="0.1.0"
        ),
        reviewed_at=datetime.now(timezone.utc),
    )


async def _run_gate(node_input, ctx_state=None):
    mock_ctx = MagicMock()
    mock_ctx.state = ctx_state or {}
    result = None
    async for item in execution_gate.run(ctx=mock_ctx, node_input=node_input):
        result = item.output
    return result


@pytest.mark.asyncio
async def test_gate_skips_when_no_hitl_decision():
    with (
        patch("orchestrator.gates.execution.FirestoreClient") as mock_fs,
        patch("orchestrator.gates.execution.emit_action_executed_audit") as mock_exec_audit,
    ):
        res = await _run_gate({})
        assert res["status"] == "skipped"
        assert res["reason"] == "no_hitl_decision"
        mock_fs.assert_not_called()
        mock_exec_audit.assert_not_called()


@pytest.mark.asyncio
async def test_gate_skips_when_hitl_rejected(sample_proposed_action):
    node_input = {
        "hitl_decision": {
            "outcome": "rejected",
            "action": sample_proposed_action.model_dump(),
        }
    }
    with (
        patch("orchestrator.gates.execution.FirestoreClient") as mock_fs,
        patch("orchestrator.gates.execution.emit_action_executed_audit") as mock_exec_audit,
    ):
        res = await _run_gate(node_input)
        assert res["status"] == "skipped"
        assert res["reason"] == "hitl_rejected"
        mock_fs.assert_not_called()
        mock_exec_audit.assert_not_called()


@pytest.mark.asyncio
async def test_gate_refuses_on_approved_verdict_absent_when_reviewer_authorized(sample_proposed_action):
    mock_executor = MagicMock()
    node_input = {
        "hitl_decision": {
            "outcome": "approved",
            "action": sample_proposed_action.model_dump(),
            "approving_user_id": "user-app-1",
        },
        "executor": mock_executor,
    }
    ctx_state = {"last_authorized_skills": [{"name": "skills/private-reviewer"}]}
    with (
        patch("orchestrator.gates.execution.FirestoreClient") as mock_fs_cls,
        patch("orchestrator.gates.execution.emit_action_failed_audit") as mock_fail_audit,
    ):
        mock_fs = mock_fs_cls.return_value
        res = await _run_gate(node_input, ctx_state=ctx_state)
        assert res["status"] == "failed"
        assert res["reason"] == "reviewer_verdict_missing_or_reviewer_revoked"

        mock_executor.submit_order.assert_not_called()
        mock_fs.update_proposed_action_status.assert_called_once_with(
            "act-exec-101",
            ActionStatus.FAILED,
        )
        mock_fail_audit.assert_called_once()


@pytest.mark.asyncio
async def test_gate_refuses_on_approved_verdict_absent_when_reviewer_unauthorized(sample_proposed_action):
    mock_executor = MagicMock()
    node_input = {
        "hitl_decision": {
            "outcome": "approved",
            "action": sample_proposed_action.model_dump(),
            "approving_user_id": "user-app-1",
        },
        "executor": mock_executor,
    }
    ctx_state = {"last_authorized_skills": []}
    with (
        patch("orchestrator.gates.execution.FirestoreClient") as mock_fs_cls,
        patch("orchestrator.gates.execution.emit_action_failed_audit") as mock_fail_audit,
    ):
        mock_fs = mock_fs_cls.return_value
        res = await _run_gate(node_input, ctx_state=ctx_state)
        assert res["status"] == "failed"
        assert res["reason"] == "reviewer_verdict_missing_or_reviewer_revoked"

        mock_executor.submit_order.assert_not_called()
        mock_fs.update_proposed_action_status.assert_called_once_with(
            "act-exec-101",
            ActionStatus.FAILED,
        )
        mock_fail_audit.assert_called_once()


@pytest.mark.asyncio
async def test_gate_executes_on_approved_verdict_absent_with_admin_bypass(sample_proposed_action, monkeypatch):
    monkeypatch.setenv("PORTFOLIO_COPILOT_ADMIN_BYPASS_REVIEWER", "true")
    mock_executor = MagicMock()
    mock_executor.submit_order.return_value = ExecutionResult(
        broker_order_id="ord-alpaca-999",
        submitted_at=datetime.now(timezone.utc),
        client_order_id="act-exec-101",
        raw_status="accepted",
    )
    node_input = {
        "hitl_decision": {
            "outcome": "approved",
            "action": sample_proposed_action.model_dump(),
            "approving_user_id": "user-app-1",
        },
        "executor": mock_executor,
    }
    with (
        patch("orchestrator.gates.execution.FirestoreClient") as mock_fs_cls,
        patch("orchestrator.gates.execution.emit_action_executed_audit") as mock_exec_audit,
    ):
        mock_fs = mock_fs_cls.return_value
        res = await _run_gate(node_input)
        assert res["status"] == "executed"
        assert res["broker_order_id"] == "ord-alpaca-999"
        assert res["action_id"] == "act-exec-101"

        mock_executor.submit_order.assert_called_once()
        mock_fs.update_proposed_action_status.assert_called_once_with(
            "act-exec-101",
            ActionStatus.EXECUTED,
            updated_fields={"broker_order_id": "ord-alpaca-999"},
        )
        mock_exec_audit.assert_called_once()


@pytest.mark.asyncio
async def test_gate_executes_on_approved_with_passing_verdict(
    sample_proposed_action, sample_reviewer_verdict
):
    mock_executor = MagicMock()
    mock_executor.submit_order.return_value = ExecutionResult(
        broker_order_id="ord-alpaca-888",
        submitted_at=datetime.now(timezone.utc),
        client_order_id="act-exec-101",
        raw_status="accepted",
    )
    node_input = {
        "hitl_decision": {
            "outcome": "approved",
            "action": sample_proposed_action.model_dump(),
        },
        "reviewer_verdict": sample_reviewer_verdict.model_dump(),
        "executor": mock_executor,
    }
    with (
        patch("orchestrator.gates.execution.FirestoreClient") as mock_fs_cls,
        patch("orchestrator.gates.execution.emit_action_executed_audit") as mock_exec_audit,
    ):
        mock_fs = mock_fs_cls.return_value
        res = await _run_gate(node_input)
        assert res["status"] == "executed"
        assert res["broker_order_id"] == "ord-alpaca-888"
        mock_executor.submit_order.assert_called_once()
        mock_fs.update_proposed_action_status.assert_called_once_with(
            "act-exec-101",
            ActionStatus.EXECUTED,
            updated_fields={"broker_order_id": "ord-alpaca-888"},
        )
        mock_exec_audit.assert_called_once()


@pytest.mark.asyncio
async def test_gate_refuses_on_approved_with_failing_verdict(
    sample_proposed_action, sample_reviewer_verdict
):
    mock_executor = MagicMock()
    failing_verdict = sample_reviewer_verdict.model_copy(update={"overall_pass": False})
    node_input = {
        "hitl_decision": {
            "outcome": "approved",
            "action": sample_proposed_action.model_dump(),
        },
        "reviewer_verdict": failing_verdict.model_dump(),
        "executor": mock_executor,
    }
    with (
        patch("orchestrator.gates.execution.FirestoreClient") as mock_fs_cls,
        patch("orchestrator.gates.execution.emit_action_failed_audit") as mock_fail_audit,
    ):
        mock_fs = mock_fs_cls.return_value
        res = await _run_gate(node_input)
        assert res["status"] == "failed"
        assert res["reason"] == "reviewer_verdict_failed"

        mock_executor.submit_order.assert_not_called()
        mock_fs.update_proposed_action_status.assert_called_once_with(
            "act-exec-101", ActionStatus.FAILED
        )
        mock_fail_audit.assert_called_once()
        assert mock_fail_audit.call_args[1]["error"] == "reviewer_verdict_failed"


@pytest.mark.asyncio
async def test_gate_handles_alpaca_execution_error(sample_proposed_action, sample_reviewer_verdict):
    mock_executor = MagicMock()
    mock_executor.submit_order.side_effect = AlpacaExecutionError("insufficient funds")
    node_input = {
        "hitl_decision": {
            "outcome": "approved",
            "action": sample_proposed_action.model_dump(),
        },
        "reviewer_verdict": sample_reviewer_verdict.model_dump(),
        "executor": mock_executor,
    }
    with (
        patch("orchestrator.gates.execution.FirestoreClient") as mock_fs_cls,
        patch("orchestrator.gates.execution.emit_action_failed_audit") as mock_fail_audit,
    ):
        mock_fs = mock_fs_cls.return_value
        res = await _run_gate(node_input)
        assert res["status"] == "failed"
        assert res["reason"] == "insufficient funds"

        mock_fs.update_proposed_action_status.assert_called_once_with(
            "act-exec-101", ActionStatus.FAILED
        )
        mock_fail_audit.assert_called_once()
        assert mock_fail_audit.call_args[1]["error"] == "insufficient funds"


@pytest.mark.asyncio
async def test_gate_handles_alpaca_credentials_missing(sample_proposed_action, sample_reviewer_verdict):
    mock_executor = MagicMock()
    mock_executor.submit_order.side_effect = AlpacaExecutionError(
        "Alpaca credentials not configured"
    )
    node_input = {
        "hitl_decision": {
            "outcome": "approved",
            "action": sample_proposed_action.model_dump(),
        },
        "reviewer_verdict": sample_reviewer_verdict.model_dump(),
        "executor": mock_executor,
    }
    with (
        patch("orchestrator.gates.execution.FirestoreClient") as mock_fs_cls,
        patch("orchestrator.gates.execution.emit_action_failed_audit") as mock_fail_audit,
    ):
        mock_fs = mock_fs_cls.return_value
        res = await _run_gate(node_input)
        assert res["status"] == "failed"
        assert "credentials not configured" in res["reason"]
        mock_fs.update_proposed_action_status.assert_called_once_with(
            "act-exec-101", ActionStatus.FAILED
        )
        mock_fail_audit.assert_called_once()


@pytest.mark.asyncio
async def test_gate_passes_approving_user_id_to_audit(sample_proposed_action, sample_reviewer_verdict):
    mock_executor = MagicMock()
    mock_executor.submit_order.return_value = ExecutionResult(
        broker_order_id="ord-alpaca-777",
        submitted_at=datetime.now(timezone.utc),
        client_order_id="act-exec-101",
        raw_status="accepted",
    )
    node_input = {
        "hitl_decision": {
            "outcome": "approved",
            "action": sample_proposed_action.model_dump(),
            "approving_user_id": "approver-xyz",
        },
        "reviewer_verdict": sample_reviewer_verdict.model_dump(),
        "executor": mock_executor,
    }
    with (
        patch("orchestrator.gates.execution.FirestoreClient"),
        patch("orchestrator.gates.execution.emit_action_executed_audit") as mock_exec_audit,
    ):
        await _run_gate(node_input)
        mock_exec_audit.assert_called_once()
        assert mock_exec_audit.call_args[1]["executing_user_id"] == "approver-xyz"


@pytest.mark.asyncio
async def test_gate_verdict_as_pydantic_model(
    sample_proposed_action, sample_reviewer_verdict
):
    mock_executor = MagicMock()
    mock_executor.submit_order.return_value = ExecutionResult(
        broker_order_id="ord-alpaca-model-1",
        submitted_at=datetime.now(timezone.utc),
        client_order_id="act-exec-101",
        raw_status="accepted",
    )
    node_input = {
        "hitl_decision": {
            "outcome": "approved",
            "action": sample_proposed_action.model_dump(),
        },
        "reviewer_verdict": sample_reviewer_verdict,
        "executor": mock_executor,
    }
    with (
        patch("orchestrator.gates.execution.FirestoreClient"),
        patch("orchestrator.gates.execution.emit_action_executed_audit"),
    ):
        res = await _run_gate(node_input)
        assert res["status"] == "executed"
        assert res["broker_order_id"] == "ord-alpaca-model-1"


@pytest.mark.asyncio
async def test_gate_malformed_hitl_decision():
    res1 = await _run_gate({"hitl_decision": "not_a_dict"})
    assert res1["status"] == "skipped"

    res2 = await _run_gate("not_a_dict")
    assert res2["status"] == "skipped"
