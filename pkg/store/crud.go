package store

import (
	"cloud.google.com/go/firestore"
	"context"
	"fmt"
	"portfolio-copilot/pkg/contracts"
)

const (
	collectionHoldings    = "holdings"
	collectionLiabilities = "liabilities"
	collectionAuditLog    = "audit_log"
	collectionIPS         = "ips"
	collectionW2Documents = "w2_documents"
)

// SetHoldings overwrites the holdings snapshot for a given user.
func (c *Client) SetHoldings(ctx context.Context, userID string, snapshot *contracts.HoldingsSnapshot) error {
	if snapshot == nil {
		return fmt.Errorf("snapshot is nil")
	}

	if err := validate(c.holdingsSchema, snapshot); err != nil {
		return fmt.Errorf("invalid holdings snapshot: %w", err)
	}

	_, err := c.fs.Collection(collectionHoldings).Doc(userID).Set(ctx, snapshot)
	if err != nil {
		return fmt.Errorf("failed to set holdings in firestore: %w", err)
	}

	return nil
}

// SetLiabilities overwrites the liabilities snapshot for a given user.
func (c *Client) SetLiabilities(ctx context.Context, userID string, snapshot *contracts.LiabilitiesSnapshot) error {
	if snapshot == nil {
		return fmt.Errorf("snapshot is nil")
	}

	if err := validate(c.liabilitiesSchema, snapshot); err != nil {
		return fmt.Errorf("invalid liabilities snapshot: %w", err)
	}

	_, err := c.fs.Collection(collectionLiabilities).Doc(userID).Set(ctx, snapshot)
	if err != nil {
		return fmt.Errorf("failed to set liabilities in firestore: %w", err)
	}

	return nil
}

// AppendAuditLog adds a new audit log entry.
func (c *Client) AppendAuditLog(ctx context.Context, entry *contracts.AuditLogEntry) error {
	if entry == nil {
		return fmt.Errorf("entry is nil")
	}

	if err := validate(c.auditLogSchema, entry); err != nil {
		return fmt.Errorf("invalid audit log entry: %w", err)
	}

	// We use the LogID as the document ID for idempotency and easier lookup
	docRef := c.fs.Collection(collectionAuditLog).Doc(entry.LogID)
	_, err := docRef.Set(ctx, entry)
	if err != nil {
		return fmt.Errorf("failed to append audit log in firestore: %w", err)
	}

	return nil
}

// UpdateIPS implements the IPS versioning invariant.
// It ensures there is exactly one active version per ips_id.
// When adding a new version, the previous active version is marked as superseded.
func (c *Client) UpdateIPS(ctx context.Context, newIPS *contracts.InvestmentPolicyStatement) error {
	if newIPS == nil {
		return fmt.Errorf("newIPS is nil")
	}

	// Always validate the incoming write first
	if err := validate(c.ipsSchema, newIPS); err != nil {
		return fmt.Errorf("invalid IPS document: %w", err)
	}

	if newIPS.Status != contracts.IPSStatusActive {
		return fmt.Errorf("new IPS must have status 'active'")
	}

	newDocID := fmt.Sprintf("%s_v%d", newIPS.IPSID, newIPS.Version)
	newDocRef := c.fs.Collection(collectionIPS).Doc(newDocID)

	err := c.fs.RunTransaction(ctx, func(ctx context.Context, tx *firestore.Transaction) error {
		// 1. Find the currently active IPS for this ips_id
		query := c.fs.Collection(collectionIPS).
			Where("ips_id", "==", newIPS.IPSID).
			Where("status", "==", contracts.IPSStatusActive).
			Limit(1)

		docs, err := tx.Documents(query).GetAll()
		if err != nil {
			return fmt.Errorf("failed to query active IPS: %w", err)
		}

		if len(docs) > 1 {
			// This shouldn't happen if the invariant was always respected, but guard against it.
			return fmt.Errorf("invariant violated: found multiple active IPS documents for ips_id %s", newIPS.IPSID)
		}

		if len(docs) == 1 {
			// There's an active IPS, supersede it
			oldDoc := docs[0]
			var oldIPS contracts.InvestmentPolicyStatement
			if err := oldDoc.DataTo(&oldIPS); err != nil {
				return fmt.Errorf("failed to parse existing IPS: %w", err)
			}

			// Prepare the update
			oldIPS.Status = contracts.IPSStatusSuperseded
			oldIPS.SupersededBy = &newDocID

			// Validate the modified old document before saving
			if err := validate(c.ipsSchema, &oldIPS); err != nil {
				return fmt.Errorf("modified old IPS fails validation: %w", err)
			}

			if err := tx.Set(oldDoc.Ref, oldIPS); err != nil {
				return fmt.Errorf("failed to supersede old IPS: %w", err)
			}
		} else {
			// Initial case: no active IPS exists.
			if newIPS.Version != 1 {
				return fmt.Errorf("no active IPS found, but new version is not 1 (got %d)", newIPS.Version)
			}
		}

		// 2. Write the new active document
		if err := tx.Set(newDocRef, newIPS); err != nil {
			return fmt.Errorf("failed to write new IPS: %w", err)
		}

		return nil
	})

	if err != nil {
		return fmt.Errorf("failed to update IPS transactionally: %w", err)
	}

	return nil
}

// SetUserProfile sets the user profile for a given user.
func (c *Client) SetUserProfile(ctx context.Context, userID string, profile *contracts.UserProfile) error {
	if profile == nil {
		return fmt.Errorf("profile is nil")
	}
	if userID == "" {
		return fmt.Errorf("userID is empty")
	}
	if profile.UserID == "" {
		profile.UserID = userID
	}

	if c.userProfileSchema != nil {
		if err := validate(c.userProfileSchema, profile); err != nil {
			return fmt.Errorf("invalid user profile: %w", err)
		}
	}

	_, err := c.fs.Collection(collectionUserProfiles).Doc(userID).Set(ctx, profile)
	if err != nil {
		return fmt.Errorf("failed to set user profile in firestore: %w", err)
	}

	return nil
}

// SetDocument records a DocumentItem in Firestore.
func (c *Client) SetDocument(ctx context.Context, item *contracts.DocumentItem) error {
	if item == nil {
		return fmt.Errorf("document item is nil")
	}
	if item.ID == "" {
		return fmt.Errorf("document item ID is empty")
	}

	_, err := c.fs.Collection(collectionDocuments).Doc(item.ID).Set(ctx, item)
	if err != nil {
		return fmt.Errorf("failed to set document in firestore: %w", err)
	}

	return nil
}

// SetW2Document saves a validated W2Document to Firestore.
func (c *Client) SetW2Document(ctx context.Context, doc *contracts.W2Document) error {
	if doc == nil {
		return fmt.Errorf("w2 document is nil")
	}
	if doc.ID == "" {
		return fmt.Errorf("w2 document ID is empty")
	}
	if doc.UserID == "" {
		return fmt.Errorf("w2 document UserID is empty")
	}

	if c.w2Schema != nil {
		if err := validate(c.w2Schema, doc); err != nil {
			return fmt.Errorf("invalid w2 document: %w", err)
		}
	}

	_, err := c.fs.Collection(collectionW2Documents).Doc(doc.ID).Set(ctx, doc)
	if err != nil {
		return fmt.Errorf("failed to set w2 document in firestore: %w", err)
	}

	return nil
}

// DeleteW2Document deletes a W2 document for a given user from Firestore.
func (c *Client) DeleteW2Document(ctx context.Context, userID string, docID string) error {
	if userID == "" || docID == "" {
		return fmt.Errorf("userID and docID must not be empty")
	}

	docRef := c.fs.Collection(collectionW2Documents).Doc(docID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		return err
	}

	var w2 contracts.W2Document
	if err := doc.DataTo(&w2); err != nil {
		return fmt.Errorf("failed to parse existing w2 document: %w", err)
	}
	if w2.UserID != userID {
		return fmt.Errorf("permission denied: w2 document does not belong to user %s", userID)
	}

	_, err = docRef.Delete(ctx)
	if err != nil {
		return fmt.Errorf("failed to delete w2 document from firestore: %w", err)
	}
	return nil
}

