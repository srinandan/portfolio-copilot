package store

import (
	"context"
	"fmt"

	"cloud.google.com/go/firestore"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"portfolio-copilot/pkg/contracts"
)

const (
	collectionSpendingReports = "spending_reports"
	collectionDriftReports    = "drift_reports"
	collectionDocuments       = "documents"
	collectionProposedActions = "proposed_actions"
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
	docRef := c.fs.Collection(collectionHoldings).Doc(userID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		return nil, err
	}
	var snapshot contracts.HoldingsSnapshot
	if err := doc.DataTo(&snapshot); err != nil {
		return nil, fmt.Errorf("failed to parse holdings snapshot: %w", err)
	}
	return &snapshot, nil
}

// GetActiveIPS reads the currently active InvestmentPolicyStatement for a given user from Firestore.
func (c *Client) GetActiveIPS(ctx context.Context, userID string) (*contracts.InvestmentPolicyStatement, error) {
	query := c.fs.Collection(collectionIPS).
		Where("user_id", "==", userID).
		Where("status", "==", contracts.IPSStatusActive).
		Limit(1)

	docs, err := query.Documents(ctx).GetAll()
	if err != nil {
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
	docRef := c.fs.Collection(collectionSpendingReports).Doc(userID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		return nil, err
	}
	var report contracts.SpendingReport
	if err := doc.DataTo(&report); err != nil {
		return nil, fmt.Errorf("failed to parse spending report: %w", err)
	}
	return &report, nil
}

// GetDriftReport reads the drift report for a given user from Firestore.
func (c *Client) GetDriftReport(ctx context.Context, userID string) (*contracts.DriftReport, error) {
	docRef := c.fs.Collection(collectionDriftReports).Doc(userID)
	doc, err := docRef.Get(ctx)
	if err != nil {
		return nil, err
	}
	var report contracts.DriftReport
	if err := doc.DataTo(&report); err != nil {
		return nil, fmt.Errorf("failed to parse drift report: %w", err)
	}
	return &report, nil
}

// GetDocuments reads uploaded document metadata items from Firestore.
func (c *Client) GetDocuments(ctx context.Context, userID string) ([]contracts.DocumentItem, error) {
	query := c.fs.Collection(collectionDocuments).Limit(50)
	docs, err := query.Documents(ctx).GetAll()
	if err != nil {
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
