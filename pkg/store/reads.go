package store

import (
	"context"
	"encoding/json"
	"fmt"

	"cloud.google.com/go/firestore"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"portfolio-copilot/pkg/contracts"
)

const (
	collectionSpendingReports = "spending_reports"
	collectionDriftReports    = "drift_reports"
	collectionDocuments       = "documents"
	collectionProposedActions = "proposed_actions"
	collectionUserProfiles    = "user_profiles"
)

// IsNotFound returns true if the error is a Firestore/gRPC NotFound error.
func IsNotFound(err error) bool {
	if err == nil {
		return false
	}
	return status.Code(err) == codes.NotFound
}

// GetHoldings reads the holdings snapshot for a given user from Firestore.
func (c *Client) GetHoldings(ctx context.Context, userID string) (*contracts.HoldingsSnapshot, error) {
	if err := ValidateUserID(userID); err != nil {
		return nil, err
	}
	ctx, span := tracer.Start(ctx, "store.GetHoldings", trace.WithAttributes(attribute.String("user_id", userID)))
	defer span.End()
	docRef := c.fs.Collection(collectionHoldings).Doc(userID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		span.RecordError(err)
		return nil, err
	}
	var snapshot contracts.HoldingsSnapshot
	if err := doc.DataTo(&snapshot); err != nil {
		dataBytes, jsonErr := json.Marshal(doc.Data())
		if jsonErr != nil {
			return nil, fmt.Errorf("failed to parse holdings snapshot: %w", err)
		}
		if jsonErr := json.Unmarshal(dataBytes, &snapshot); jsonErr != nil {
			return nil, fmt.Errorf("failed to parse holdings snapshot: %w", err)
		}
	}
	return &snapshot, nil
}

// GetLiabilities reads the liabilities snapshot for a given user from Firestore.
func (c *Client) GetLiabilities(ctx context.Context, userID string) (*contracts.LiabilitiesSnapshot, error) {
	if err := ValidateUserID(userID); err != nil {
		return nil, err
	}
	ctx, span := tracer.Start(ctx, "store.GetLiabilities", trace.WithAttributes(attribute.String("user_id", userID)))
	defer span.End()
	docRef := c.fs.Collection(collectionLiabilities).Doc(userID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		span.RecordError(err)
		return nil, err
	}
	var snapshot contracts.LiabilitiesSnapshot
	if err := doc.DataTo(&snapshot); err != nil {
		dataBytes, jsonErr := json.Marshal(doc.Data())
		if jsonErr != nil {
			return nil, fmt.Errorf("failed to parse liabilities snapshot: %w", err)
		}
		if jsonErr := json.Unmarshal(dataBytes, &snapshot); jsonErr != nil {
			return nil, fmt.Errorf("failed to parse liabilities snapshot: %w", err)
		}
	}
	return &snapshot, nil
}

// GetActiveIPS reads the currently active InvestmentPolicyStatement for a given user from Firestore.
func (c *Client) GetActiveIPS(ctx context.Context, userID string) (*contracts.InvestmentPolicyStatement, error) {
	if err := ValidateUserID(userID); err != nil {
		return nil, err
	}
	ctx, span := tracer.Start(ctx, "store.GetActiveIPS", trace.WithAttributes(attribute.String("user_id", userID)))
	defer span.End()
	query := c.fs.Collection(collectionIPS).
		Where("user_id", "==", userID).
		Where("status", "==", contracts.IPSStatusActive).
		Limit(1)

	docs, err := query.Documents(ctx).GetAll()
	if err != nil {
		span.RecordError(err)
		return nil, err
	}
	if len(docs) == 0 {
		return nil, status.Error(codes.NotFound, fmt.Sprintf("no active IPS found for user %s", userID))
	}
	var ips contracts.InvestmentPolicyStatement
	if err := docs[0].DataTo(&ips); err != nil {
		return nil, fmt.Errorf("failed to parse active IPS: %w", err)
	}
	return &ips, nil
}

// GetSpendingReport reads the spending report for a given user from Firestore.
func (c *Client) GetSpendingReport(ctx context.Context, userID string) (*contracts.SpendingReport, error) {
	if err := ValidateUserID(userID); err != nil {
		return nil, err
	}
	ctx, span := tracer.Start(ctx, "store.GetSpendingReport", trace.WithAttributes(attribute.String("user_id", userID)))
	defer span.End()
	docRef := c.fs.Collection(collectionSpendingReports).Doc(userID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		span.RecordError(err)
		return nil, err
	}
	var report contracts.SpendingReport
	if err := doc.DataTo(&report); err != nil {
		dataBytes, jsonErr := json.Marshal(doc.Data())
		if jsonErr != nil {
			return nil, fmt.Errorf("failed to parse spending report: %w", err)
		}
		if jsonErr := json.Unmarshal(dataBytes, &report); jsonErr != nil {
			return nil, fmt.Errorf("failed to parse spending report: %w", err)
		}
	}
	return &report, nil
}

// GetDriftReport reads the drift report for a given user from Firestore.
func (c *Client) GetDriftReport(ctx context.Context, userID string) (*contracts.DriftReport, error) {
	if err := ValidateUserID(userID); err != nil {
		return nil, err
	}
	ctx, span := tracer.Start(ctx, "store.GetDriftReport", trace.WithAttributes(attribute.String("user_id", userID)))
	defer span.End()
	docRef := c.fs.Collection(collectionDriftReports).Doc(userID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		span.RecordError(err)
		return nil, err
	}
	var report contracts.DriftReport
	if err := doc.DataTo(&report); err != nil {
		dataBytes, jsonErr := json.Marshal(doc.Data())
		if jsonErr != nil {
			return nil, fmt.Errorf("failed to parse drift report: %w", err)
		}
		if jsonErr := json.Unmarshal(dataBytes, &report); jsonErr != nil {
			return nil, fmt.Errorf("failed to parse drift report: %w", err)
		}
	}
	return &report, nil
}

// GetDocuments reads uploaded document metadata items for a given user from Firestore.
func (c *Client) GetDocuments(ctx context.Context, userID string) ([]contracts.DocumentItem, error) {
	if err := ValidateUserID(userID); err != nil {
		return nil, err
	}
	ctx, span := tracer.Start(ctx, "store.GetDocuments", trace.WithAttributes(attribute.String("user_id", userID)))
	defer span.End()
	query := c.fs.Collection(collectionDocuments).Where("user_id", "==", userID).Limit(50)
	docs, err := query.Documents(ctx).GetAll()
	if err != nil {
		span.RecordError(err)
		return nil, err
	}
	items := make([]contracts.DocumentItem, 0, len(docs))
	for _, doc := range docs {
		var item contracts.DocumentItem
		if err := doc.DataTo(&item); err == nil {
			items = append(items, item)
		}
	}
	return items, nil
}

// GetProposedAction reads a proposed action by action_id from Firestore.
func (c *Client) GetProposedAction(ctx context.Context, actionID string) (*contracts.ProposedAction, error) {
	docRef := c.fs.Collection(collectionProposedActions).Doc(actionID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		return nil, err
	}
	var action contracts.ProposedAction
	if err := doc.DataTo(&action); err != nil {
		return nil, fmt.Errorf("failed to parse proposed action: %w", err)
	}
	return &action, nil
}

// UpdateProposedActionStatus updates the status of an existing proposed action in Firestore.
func (c *Client) UpdateProposedActionStatus(ctx context.Context, actionID string, newStatus contracts.ActionStatus) error {
	docRef := c.fs.Collection(collectionProposedActions).Doc(actionID)
	_, err := docRef.Update(ctx, []firestore.Update{
		{Path: "status", Value: string(newStatus)},
	})
	if err != nil {
		return fmt.Errorf("failed to update proposed action status: %w", err)
	}
	return nil
}

// GetUserProfile reads the user profile for a given user from Firestore.
func (c *Client) GetUserProfile(ctx context.Context, userID string) (*contracts.UserProfile, error) {
	if err := ValidateUserID(userID); err != nil {
		return nil, err
	}
	ctx, span := tracer.Start(ctx, "store.GetUserProfile", trace.WithAttributes(attribute.String("user_id", userID)))
	defer span.End()
	docRef := c.fs.Collection(collectionUserProfiles).Doc(userID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		span.RecordError(err)
		return nil, err
	}
	var profile contracts.UserProfile
	if err := doc.DataTo(&profile); err != nil {
		dataBytes, jsonErr := json.Marshal(doc.Data())
		if jsonErr != nil {
			return nil, fmt.Errorf("failed to parse user profile: %w", err)
		}
		if jsonErr := json.Unmarshal(dataBytes, &profile); jsonErr != nil {
			return nil, fmt.Errorf("failed to parse user profile: %w", err)
		}
	}
	return &profile, nil
}

// GetW2Documents reads all W-2 documents for a given user from Firestore.
func (c *Client) GetW2Documents(ctx context.Context, userID string) ([]contracts.W2Document, error) {
	if err := ValidateUserID(userID); err != nil {
		return nil, err
	}
	ctx, span := tracer.Start(ctx, "store.GetW2Documents", trace.WithAttributes(attribute.String("user_id", userID)))
	defer span.End()

	query := c.fs.Collection(collectionW2Documents).Where("user_id", "==", userID).Limit(50)
	docs, err := query.Documents(ctx).GetAll()
	if err != nil {
		span.RecordError(err)
		return nil, err
	}

	items := make([]contracts.W2Document, 0, len(docs))
	for _, doc := range docs {
		var item contracts.W2Document
		if err := doc.DataTo(&item); err == nil {
			items = append(items, item)
		} else {
			dataBytes, jsonErr := json.Marshal(doc.Data())
			if jsonErr == nil && json.Unmarshal(dataBytes, &item) == nil {
				items = append(items, item)
			}
		}
	}
	return items, nil
}

// GetW2Document reads a single W-2 document by docID for a user from Firestore.
func (c *Client) GetW2Document(ctx context.Context, userID string, docID string) (*contracts.W2Document, error) {
	if err := ValidateUserID(userID); err != nil {
		return nil, err
	}
	ctx, span := tracer.Start(ctx, "store.GetW2Document", trace.WithAttributes(
		attribute.String("user_id", userID),
		attribute.String("doc_id", docID),
	))
	defer span.End()

	docRef := c.fs.Collection(collectionW2Documents).Doc(docID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		span.RecordError(err)
		return nil, err
	}

	var item contracts.W2Document
	if err := doc.DataTo(&item); err != nil {
		dataBytes, jsonErr := json.Marshal(doc.Data())
		if jsonErr != nil {
			return nil, fmt.Errorf("failed to parse w2 document: %w", err)
		}
		if jsonErr := json.Unmarshal(dataBytes, &item); jsonErr != nil {
			return nil, fmt.Errorf("failed to parse w2 document: %w", err)
		}
	}

	if item.UserID != userID {
		return nil, status.Error(codes.NotFound, fmt.Sprintf("w2 document %s not found", docID))
	}

	return &item, nil
}

