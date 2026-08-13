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

COLLECTION_HOLDINGS = "holdings"
COLLECTION_LIABILITIES = "liabilities"
COLLECTION_AUDIT_LOG = "audit_log"
COLLECTION_IPS = "ips"
COLLECTION_PROPOSED_ACTIONS = "proposed_actions"
COLLECTION_SPENDING_REPORTS = "spending_reports"


def _default_dict_factory(obj: Any) -> dict[str, Any]:
    return json.loads(obj.model_dump_json(exclude_none=True))


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
    def __init__(self, project: str | None = None):
        self.project = (
            project or os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "test-project"
        )

        # In test environments (emulator), we need to handle credentials differently
        emulator_host = os.environ.get("FIRESTORE_EMULATOR_HOST")
        if emulator_host:
            self.db = firestore.Client(project=self.project, credentials=AnonymousCredentials())
        else:
            self.db = firestore.Client(project=self.project)

    def _dict_factory(self, obj: Any) -> dict[str, Any]:
        """Convert a Pydantic model to a dict, handling dates/enums properly for Firestore."""
        # We rely on Pydantic's model_dump with mode="json" to serialize enums/dates to primitives.
        return json.loads(obj.model_dump_json(exclude_none=True))

    def get_holdings(self, user_id: str) -> HoldingsSnapshot | None:
        """Gets the holdings snapshot for a given user."""
        doc_ref = self.db.collection(COLLECTION_HOLDINGS).document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return HoldingsSnapshot.model_validate(doc.to_dict())
        return None

    def set_holdings(self, user_id: str, snapshot: HoldingsSnapshot) -> None:
        """Overwrites the holdings snapshot for a given user."""
        doc_ref = self.db.collection(COLLECTION_HOLDINGS).document(user_id)
        doc_ref.set(self._dict_factory(snapshot))

    def set_liabilities(self, user_id: str, snapshot: LiabilitiesSnapshot) -> None:
        """Overwrites the liabilities snapshot for a given user."""
        doc_ref = self.db.collection(COLLECTION_LIABILITIES).document(user_id)
        data = self._dict_factory(snapshot)
        doc_ref.set(data)

    def get_liabilities(self, user_id: str) -> LiabilitiesSnapshot | None:
        """Gets the liabilities snapshot for a given user."""
        doc_ref = self.db.collection(COLLECTION_LIABILITIES).document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return LiabilitiesSnapshot.model_validate(doc.to_dict())
        return None

    def set_proposed_action(self, action: ProposedAction) -> None:
        """Writes a ProposedAction to Firestore, keyed by action_id."""
        doc_ref = self.db.collection(COLLECTION_PROPOSED_ACTIONS).document(action.action_id)
        doc_ref.set(self._dict_factory(action))

    def get_proposed_action(self, action_id: str) -> ProposedAction | None:
        """Reads a ProposedAction by action_id."""
        doc_ref = self.db.collection(COLLECTION_PROPOSED_ACTIONS).document(action_id)
        doc = doc_ref.get()
        if doc.exists:
            return ProposedAction.model_validate(doc.to_dict())
        return None

    def update_proposed_action_status(
        self, action_id: str, new_status: ActionStatus, updated_fields: dict[str, Any] | None = None
    ) -> None:
        """Updates the status (and optionally other fields) of a stored ProposedAction.

        Uses `update()` rather than `set()` so partial writes are safe under concurrent access.
        """
        doc_ref = self.db.collection(COLLECTION_PROPOSED_ACTIONS).document(action_id)
        updates: dict[str, Any] = {"status": new_status.value}
        if updated_fields:
            updates.update(updated_fields)
        doc_ref.update(updates)

    def append_audit_log(self, entry: AuditLogEntry) -> None:
        """Adds a new audit log entry."""
        # Use the log_id as the document ID for idempotency
        doc_ref = self.db.collection(COLLECTION_AUDIT_LOG).document(entry.log_id)
        data = self._dict_factory(entry)
        doc_ref.set(data)

    def get_active_ips(self, ips_id: str) -> InvestmentPolicyStatement | None:
        """Gets the currently active IPS for a given ips_id."""
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

    def update_ips(self, new_ips: InvestmentPolicyStatement) -> None:
        """
        Implements the IPS versioning invariant.
        Ensures there is exactly one active version per ips_id.
        When adding a new version, the previous active version is marked as superseded.
        """
        transaction = self.db.transaction()
        _update_ips_transactional(transaction, self.db, new_ips, self._dict_factory)

    def get_active_ips_by_user(self, user_id: str) -> InvestmentPolicyStatement | None:
        """Gets the currently active IPS for a given user_id."""
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

    def set_spending_report(self, user_id: str, report: Any) -> None:
        """Writes a SpendingReport to Firestore, keyed by user_id."""
        doc_ref = self.db.collection(COLLECTION_SPENDING_REPORTS).document(user_id)
        if isinstance(report, dict):
            data = report
        elif hasattr(report, "model_dump"):
            data = self._dict_factory(report)
        else:
            data = dict(report)
        doc_ref.set(data)

    def get_spending_report(self, user_id: str) -> dict[str, Any] | None:
        """Reads a SpendingReport dict by user_id."""
        doc_ref = self.db.collection(COLLECTION_SPENDING_REPORTS).document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
