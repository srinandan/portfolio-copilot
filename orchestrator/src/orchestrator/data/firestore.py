import json
import os
from typing import Any

from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore
from google.cloud.firestore_v1.transaction import Transaction

from ..contracts import (
    ActionStatus,
    AuditLogEntry,
    HoldingsSnapshot,
    InvestmentPolicyStatement,
    IPSStatus,
    LiabilitiesSnapshot,
    ProposedAction,
)
from ..logger import get_logger
from .firestore_mcp import FirestoreMCPClient

logger = get_logger(__name__)

COLLECTION_HOLDINGS = "holdings"
COLLECTION_LIABILITIES = "liabilities"
COLLECTION_AUDIT_LOG = "audit_log"
COLLECTION_IPS = "ips"
COLLECTION_PROPOSED_ACTIONS = "proposed_actions"
COLLECTION_SPENDING_REPORTS = "spending_reports"
COLLECTION_DRIFT_REPORTS = "drift_reports"
COLLECTION_USER_PROFILES = "user_profiles"


def _default_dict_factory(obj: Any) -> dict[str, Any]:
    return json.loads(obj.model_dump_json(by_alias=True, exclude_none=True))


@firestore.transactional
def _update_ips_transactional(
    transaction: Transaction,
    db: firestore.Client,
    new_ips: InvestmentPolicyStatement,
    dict_factory: Any = None,
) -> None:
    factory = dict_factory or _default_dict_factory

    if new_ips.status != IPSStatus.ACTIVE:
        raise ValueError("new IPS must have status 'active'")

    ips_collection = db.collection(COLLECTION_IPS)
    new_doc_id = f"{new_ips.ips_id}_v{new_ips.version}"
    new_doc_ref = ips_collection.document(new_doc_id)

    # 1. Find the currently active IPS for this ips_id
    query = (
        ips_collection.where(filter=firestore.FieldFilter("ips_id", "==", new_ips.ips_id))
        .where(filter=firestore.FieldFilter("status", "==", IPSStatus.ACTIVE.value))
        .limit(1)
    )

    docs = list(query.stream(transaction=transaction))
    if len(docs) > 1:
        raise ValueError(f"invariant violated: found multiple active IPS documents for ips_id {new_ips.ips_id}")

    if len(docs) == 1:
        # There's an active IPS, supersede it
        old_doc = docs[0]
        old_data = old_doc.to_dict()

        # Prepare the update
        old_data["status"] = IPSStatus.SUPERSEDED.value
        old_data["superseded_by"] = new_doc_id

        # Validate the modified old document before saving
        old_ips = InvestmentPolicyStatement.model_validate(old_data)

        transaction.set(old_doc.reference, factory(old_ips))
    else:
        # Initial case: no active IPS exists.
        if new_ips.version != 1:
            raise ValueError(f"no active IPS found, but new version is not 1 (got {new_ips.version})")

    # 2. Write the new active document
    transaction.set(new_doc_ref, factory(new_ips))


class FirestoreClient:
    """Hybrid Firestore client supporting Firestore Remote MCP Server with native SDK fallback.

    Default operations route through Firestore Remote MCP (https://firestore.googleapis.com/mcp)
    to participate in distributed tracing (CLIENT spans, W3C traceparent propagation).
    Native SDK methods are intentionally retained for offline/emulator environments and
    multi-document ACID transactions (_update_ips_transactional per ADR-0023).
    """

    def __init__(
        self,
        project: str | None = None,
        use_mcp: bool | None = None,
        credentials: Any = None,
    ):
        self.project = (
            project or os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "test-project"
        )
        self.credentials = credentials

        # Emulator or explicit FIRESTORE_USE_MCP=false disables MCP mode
        emulator_host = os.environ.get("FIRESTORE_EMULATOR_HOST")
        env_use_mcp = os.environ.get("FIRESTORE_USE_MCP", "true").lower() not in ("0", "false", "no")

        if use_mcp is not None:
            self.use_mcp = use_mcp
        elif emulator_host:
            self.use_mcp = False
        else:
            self.use_mcp = env_use_mcp

        # Direct native SDK client for fallback & multi-document ACID transactions
        if emulator_host:
            self.db = firestore.Client(project=self.project, credentials=AnonymousCredentials())
        elif self.credentials is not None:
            self.db = firestore.Client(project=self.project, credentials=self.credentials)
        else:
            try:
                self.db = firestore.Client(project=self.project)
            except Exception:
                self.db = firestore.Client(project=self.project, credentials=AnonymousCredentials())

        # MCP client instance for remote MCP operations
        self.mcp_client = (
            FirestoreMCPClient(project=self.project, credentials=self.credentials) if self.use_mcp else None
        )

    def _dict_factory(self, obj: Any) -> dict[str, Any]:
        """Convert a Pydantic model to a dict, handling dates/enums properly for Firestore."""
        return json.loads(obj.model_dump_json(by_alias=True, exclude_none=True))

    # =========================================================================
    # Holdings Snapshot
    # =========================================================================

    def get_holdings(self, user_id: str) -> HoldingsSnapshot | None:
        """Gets the holdings snapshot for a given user."""
        if self.use_mcp and self.mcp_client:
            try:
                data = self.mcp_client.get_document(COLLECTION_HOLDINGS, user_id)
                if data:
                    return HoldingsSnapshot.model_validate(data)
                return None
            except Exception as e:
                logger.warning("Firestore MCP get_holdings failed (%s); falling back to direct SDK", e)

        return self._get_holdings_direct(user_id)

    def set_holdings(self, user_id: str, snapshot: HoldingsSnapshot) -> None:
        """Overwrites the holdings snapshot for a given user."""
        if self.use_mcp and self.mcp_client:
            try:
                self.mcp_client.set_document(COLLECTION_HOLDINGS, user_id, self._dict_factory(snapshot))
                return
            except Exception as e:
                logger.warning("Firestore MCP set_holdings failed (%s); falling back to direct SDK", e)

        self._set_holdings_direct(user_id, snapshot)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    # Preserved intentionally for offline/emulator testing and emergency non-MCP fallback.
    def _get_holdings_direct(self, user_id: str) -> HoldingsSnapshot | None:
        doc_ref = self.db.collection(COLLECTION_HOLDINGS).document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return HoldingsSnapshot.model_validate(doc.to_dict())
        return None

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _set_holdings_direct(self, user_id: str, snapshot: HoldingsSnapshot) -> None:
        doc_ref = self.db.collection(COLLECTION_HOLDINGS).document(user_id)
        doc_ref.set(self._dict_factory(snapshot))

    # =========================================================================
    # Liabilities Snapshot
    # =========================================================================

    def get_liabilities(self, user_id: str) -> LiabilitiesSnapshot | None:
        """Gets the liabilities snapshot for a given user."""
        if self.use_mcp and self.mcp_client:
            try:
                data = self.mcp_client.get_document(COLLECTION_LIABILITIES, user_id)
                if data:
                    return LiabilitiesSnapshot.model_validate(data)
                return None
            except Exception as e:
                logger.warning("Firestore MCP get_liabilities failed (%s); falling back to direct SDK", e)

        return self._get_liabilities_direct(user_id)

    def set_liabilities(self, user_id: str, snapshot: LiabilitiesSnapshot) -> None:
        """Overwrites the liabilities snapshot for a given user."""
        if self.use_mcp and self.mcp_client:
            try:
                self.mcp_client.set_document(COLLECTION_LIABILITIES, user_id, self._dict_factory(snapshot))
                return
            except Exception as e:
                logger.warning("Firestore MCP set_liabilities failed (%s); falling back to direct SDK", e)

        self._set_liabilities_direct(user_id, snapshot)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _get_liabilities_direct(self, user_id: str) -> LiabilitiesSnapshot | None:
        doc_ref = self.db.collection(COLLECTION_LIABILITIES).document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return LiabilitiesSnapshot.model_validate(doc.to_dict())
        return None

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _set_liabilities_direct(self, user_id: str, snapshot: LiabilitiesSnapshot) -> None:
        doc_ref = self.db.collection(COLLECTION_LIABILITIES).document(user_id)
        doc_ref.set(self._dict_factory(snapshot))

    # =========================================================================
    # Proposed Actions
    # =========================================================================

    def get_proposed_action(self, action_id: str) -> ProposedAction | None:
        """Reads a ProposedAction by action_id."""
        if self.use_mcp and self.mcp_client:
            try:
                data = self.mcp_client.get_document(COLLECTION_PROPOSED_ACTIONS, action_id)
                if data:
                    return ProposedAction.model_validate(data)
                return None
            except Exception as e:
                logger.warning("Firestore MCP get_proposed_action failed (%s); falling back to direct SDK", e)

        return self._get_proposed_action_direct(action_id)

    def set_proposed_action(self, action: ProposedAction) -> None:
        """Writes a ProposedAction to Firestore, keyed by action_id."""
        if self.use_mcp and self.mcp_client:
            try:
                self.mcp_client.set_document(COLLECTION_PROPOSED_ACTIONS, action.action_id, self._dict_factory(action))
                return
            except Exception as e:
                logger.warning("Firestore MCP set_proposed_action failed (%s); falling back to direct SDK", e)

        self._set_proposed_action_direct(action)

    def update_proposed_action_status(
        self, action_id: str, new_status: ActionStatus, updated_fields: dict[str, Any] | None = None
    ) -> None:
        """Updates the status (and optionally other fields) of a stored ProposedAction."""
        if self.use_mcp and self.mcp_client:
            try:
                updates: dict[str, Any] = {"status": new_status.value}
                if updated_fields:
                    updates.update(updated_fields)
                self.mcp_client.update_document(COLLECTION_PROPOSED_ACTIONS, action_id, updates)
                return
            except Exception as e:
                logger.warning("Firestore MCP update_proposed_action_status failed (%s); falling back to direct SDK", e)

        self._update_proposed_action_status_direct(action_id, new_status, updated_fields)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _get_proposed_action_direct(self, action_id: str) -> ProposedAction | None:
        doc_ref = self.db.collection(COLLECTION_PROPOSED_ACTIONS).document(action_id)
        doc = doc_ref.get()
        if doc.exists:
            return ProposedAction.model_validate(doc.to_dict())
        return None

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _set_proposed_action_direct(self, action: ProposedAction) -> None:
        doc_ref = self.db.collection(COLLECTION_PROPOSED_ACTIONS).document(action.action_id)
        doc_ref.set(self._dict_factory(action))

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _update_proposed_action_status_direct(
        self, action_id: str, new_status: ActionStatus, updated_fields: dict[str, Any] | None = None
    ) -> None:
        doc_ref = self.db.collection(COLLECTION_PROPOSED_ACTIONS).document(action_id)
        updates: dict[str, Any] = {"status": new_status.value}
        if updated_fields:
            updates.update(updated_fields)
        doc_ref.update(updates)

    # =========================================================================
    # Audit Log
    # =========================================================================

    def append_audit_log(self, entry: AuditLogEntry) -> None:
        """Adds a new audit log entry."""
        if self.use_mcp and self.mcp_client:
            try:
                self.mcp_client.set_document(COLLECTION_AUDIT_LOG, entry.log_id, self._dict_factory(entry))
                return
            except Exception as e:
                logger.warning("Firestore MCP append_audit_log failed (%s); falling back to direct SDK", e)

        self._append_audit_log_direct(entry)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _append_audit_log_direct(self, entry: AuditLogEntry) -> None:
        doc_ref = self.db.collection(COLLECTION_AUDIT_LOG).document(entry.log_id)
        data = self._dict_factory(entry)
        doc_ref.set(data)

    # =========================================================================
    # Investment Policy Statement (IPS)
    # =========================================================================

    def get_active_ips(self, ips_id: str) -> InvestmentPolicyStatement | None:
        """Gets the currently active IPS for a given ips_id."""
        if self.use_mcp and self.mcp_client:
            try:
                docs = self.mcp_client.list_documents(COLLECTION_IPS)
                matching = [d for d in docs if d.get("ips_id") == ips_id and d.get("status") == IPSStatus.ACTIVE.value]
                if matching:
                    return InvestmentPolicyStatement.model_validate(matching[0])
                return None
            except Exception as e:
                logger.warning("Firestore MCP get_active_ips failed (%s); falling back to direct SDK", e)

        return self._get_active_ips_direct(ips_id)

    def get_active_ips_by_user(self, user_id: str) -> InvestmentPolicyStatement | None:
        """Gets the currently active IPS for a given user_id."""
        if self.use_mcp and self.mcp_client:
            try:
                docs = self.mcp_client.list_documents(COLLECTION_IPS)
                matching = [
                    d for d in docs if d.get("user_id") == user_id and d.get("status") == IPSStatus.ACTIVE.value
                ]
                if len(matching) > 1:
                    raise ValueError(f"invariant violated: found multiple active IPS documents for user_id {user_id}")
                if len(matching) == 1:
                    return InvestmentPolicyStatement.model_validate(matching[0])
                return None
            except Exception as e:
                if "invariant violated" in str(e):
                    raise
                logger.warning("Firestore MCP get_active_ips_by_user failed (%s); falling back to direct SDK", e)

        return self._get_active_ips_by_user_direct(user_id)

    def update_ips(self, new_ips: InvestmentPolicyStatement) -> None:
        """
        Implements the IPS versioning invariant.
        Ensures there is exactly one active version per ips_id.
        Multi-document atomic transaction executed via native SDK per ADR-0023.
        """
        transaction = self.db.transaction()
        _update_ips_transactional(transaction, self.db, new_ips, self._dict_factory)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _get_active_ips_direct(self, ips_id: str) -> InvestmentPolicyStatement | None:
        query = (
            self.db.collection(COLLECTION_IPS)
            .where(filter=firestore.FieldFilter("ips_id", "==", ips_id))
            .where(filter=firestore.FieldFilter("status", "==", IPSStatus.ACTIVE.value))
            .limit(1)
        )
        docs = list(query.stream())
        if docs:
            return InvestmentPolicyStatement.model_validate(docs[0].to_dict())
        return None

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _get_active_ips_by_user_direct(self, user_id: str) -> InvestmentPolicyStatement | None:
        query = (
            self.db.collection(COLLECTION_IPS)
            .where(filter=firestore.FieldFilter("user_id", "==", user_id))
            .where(filter=firestore.FieldFilter("status", "==", IPSStatus.ACTIVE.value))
        )
        docs = list(query.stream())
        if len(docs) > 1:
            raise ValueError(f"invariant violated: found multiple active IPS documents for user_id {user_id}")
        if len(docs) == 1:
            return InvestmentPolicyStatement.model_validate(docs[0].to_dict())
        return None

    # =========================================================================
    # Spending Reports
    # =========================================================================

    def set_spending_report(self, user_id: str, report: Any) -> None:
        """Writes a SpendingReport to Firestore, keyed by user_id."""
        data = (
            self._dict_factory(report)
            if hasattr(report, "model_dump")
            else (report if isinstance(report, dict) else dict(report))
        )
        if self.use_mcp and self.mcp_client:
            try:
                self.mcp_client.set_document(COLLECTION_SPENDING_REPORTS, user_id, data)
                return
            except Exception as e:
                logger.warning("Firestore MCP set_spending_report failed (%s); falling back to direct SDK", e)

        self._set_spending_report_direct(user_id, report)

    def get_spending_report(self, user_id: str) -> dict[str, Any] | None:
        """Reads a SpendingReport dict by user_id."""
        if self.use_mcp and self.mcp_client:
            try:
                return self.mcp_client.get_document(COLLECTION_SPENDING_REPORTS, user_id)
            except Exception as e:
                logger.warning("Firestore MCP get_spending_report failed (%s); falling back to direct SDK", e)

        return self._get_spending_report_direct(user_id)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _set_spending_report_direct(self, user_id: str, report: Any) -> None:
        doc_ref = self.db.collection(COLLECTION_SPENDING_REPORTS).document(user_id)
        data = (
            self._dict_factory(report)
            if hasattr(report, "model_dump")
            else (report if isinstance(report, dict) else dict(report))
        )
        doc_ref.set(data)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _get_spending_report_direct(self, user_id: str) -> dict[str, Any] | None:
        doc_ref = self.db.collection(COLLECTION_SPENDING_REPORTS).document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    # =========================================================================
    # Drift Reports
    # =========================================================================

    def set_drift_report(self, user_id: str, report: Any) -> None:
        """Writes a DriftReport to Firestore, keyed by user_id."""
        data = (
            self._dict_factory(report)
            if hasattr(report, "model_dump")
            else (report if isinstance(report, dict) else dict(report))
        )
        if self.use_mcp and self.mcp_client:
            try:
                self.mcp_client.set_document(COLLECTION_DRIFT_REPORTS, user_id, data)
                return
            except Exception as e:
                logger.warning("Firestore MCP set_drift_report failed (%s); falling back to direct SDK", e)

        self._set_drift_report_direct(user_id, report)

    def get_drift_report(self, user_id: str) -> dict[str, Any] | None:
        """Reads a DriftReport dict by user_id."""
        if self.use_mcp and self.mcp_client:
            try:
                return self.mcp_client.get_document(COLLECTION_DRIFT_REPORTS, user_id)
            except Exception as e:
                logger.warning("Firestore MCP get_drift_report failed (%s); falling back to direct SDK", e)

        return self._get_drift_report_direct(user_id)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _set_drift_report_direct(self, user_id: str, report: Any) -> None:
        doc_ref = self.db.collection(COLLECTION_DRIFT_REPORTS).document(user_id)
        data = (
            self._dict_factory(report)
            if hasattr(report, "model_dump")
            else (report if isinstance(report, dict) else dict(report))
        )
        doc_ref.set(data)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _get_drift_report_direct(self, user_id: str) -> dict[str, Any] | None:
        doc_ref = self.db.collection(COLLECTION_DRIFT_REPORTS).document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    # =========================================================================
    # User Profile
    # =========================================================================

    def set_user_profile(self, user_id: str, profile: Any) -> None:
        """Writes a UserProfile to Firestore, keyed by user_id."""
        data = (
            self._dict_factory(profile)
            if hasattr(profile, "model_dump")
            else (profile if isinstance(profile, dict) else dict(profile))
        )
        if self.use_mcp and self.mcp_client:
            try:
                self.mcp_client.set_document(COLLECTION_USER_PROFILES, user_id, data)
                return
            except Exception as e:
                logger.warning("Firestore MCP set_user_profile failed (%s); falling back to direct SDK", e)

        self._set_user_profile_direct(user_id, profile)

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        """Reads a UserProfile dict by user_id."""
        if self.use_mcp and self.mcp_client:
            try:
                return self.mcp_client.get_document(COLLECTION_USER_PROFILES, user_id)
            except Exception as e:
                logger.warning("Firestore MCP get_user_profile failed (%s); falling back to direct SDK", e)

        return self._get_user_profile_direct(user_id)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _set_user_profile_direct(self, user_id: str, profile: Any) -> None:
        doc_ref = self.db.collection(COLLECTION_USER_PROFILES).document(user_id)
        data = (
            self._dict_factory(profile)
            if hasattr(profile, "model_dump")
            else (profile if isinstance(profile, dict) else dict(profile))
        )
        doc_ref.set(data)

    # PURPOSEFUL RETENTION: Direct native google-cloud-firestore SDK implementation.
    def _get_user_profile_direct(self, user_id: str) -> dict[str, Any] | None:
        doc_ref = self.db.collection(COLLECTION_USER_PROFILES).document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
