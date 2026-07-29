package store

import (
	"context"
	"os"
	"testing"
	"time"

	"portfolio-copilot/pkg/contracts"
)

// setupTestClient ensures the Firestore emulator is running and sets up a client.
// It relies on FIRESTORE_EMULATOR_HOST being set.
func setupTestClient(t *testing.T) (*Client, context.Context) {
	t.Helper()
	if os.Getenv("FIRESTORE_EMULATOR_HOST") == "" {
		t.Skip("Skipping test: FIRESTORE_EMULATOR_HOST not set")
	}

	// Override PROJECT_ID for the emulator client
	os.Setenv("PROJECT_ID", "demo-test-project")

	ctx := context.Background()
	c, err := NewClient(ctx)
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	t.Cleanup(func() {
		c.Close()
	})
	return c, ctx
}

func ptrString(s string) *string { return &s }

func TestUpdateIPSTransaction(t *testing.T) {
	c, ctx := setupTestClient(t)

	// Clean up collection before test
	docs, err := c.fs.Collection(collectionIPS).Documents(ctx).GetAll()
	if err == nil {
		for _, doc := range docs {
			doc.Ref.Delete(ctx)
		}

		// give firestore emulator a little time to sync deletes
		time.Sleep(500 * time.Millisecond)
	}

	baseIPS := func(version int) *contracts.InvestmentPolicyStatement {
		return &contracts.InvestmentPolicyStatement{
			IPSID:            "userA_ips",
			UserID:           "userA",
			Version:          version,
			Status:           contracts.IPSStatusActive,
			EffectiveDate:    time.Now().Format("2006-01-02"),
			RiskTolerance:    contracts.RiskToleranceModerate,
			TimeHorizonYears: 10,
			TargetAllocation: []contracts.AllocationBand{
				{AssetClass: "equity", TargetPercent: 60, MinPercent: 50, MaxPercent: 70},
				{AssetClass: "bonds", TargetPercent: 30, MinPercent: 20, MaxPercent: 40},
				{AssetClass: "cash", TargetPercent: 10, MinPercent: 5, MaxPercent: 15},
			},
			Constraints: contracts.Constraints{
				ConcentrationLimitPercent: 15,
			},
			CreatedAt: time.Now().UTC().Truncate(time.Second),
		}
	}

	t.Run("initial creation", func(t *testing.T) {
		ips := baseIPS(1)
		err := c.UpdateIPS(ctx, ips)
		if err != nil {
			t.Fatalf("expected no error, got: %v", err)
		}

		// Verify exactly one active document
		docs, err := c.fs.Collection(collectionIPS).Where("ips_id", "==", "userA_ips").Where("status", "==", contracts.IPSStatusActive).Documents(ctx).GetAll()
		if err != nil {
			t.Fatalf("query failed: %v", err)
		}
		if len(docs) != 1 {
			t.Fatalf("expected 1 active doc, got %d", len(docs))
		}
	})

	t.Run("persisted field names match schema (raw document check)", func(t *testing.T) {
		docs, err := c.fs.Collection(collectionIPS).
			Where("ips_id", "==", "userA_ips").
			Where("status", "==", contracts.IPSStatusActive).
			Documents(ctx).GetAll()
		if err != nil {
			t.Fatalf("query failed: %v", err)
		}
		if len(docs) != 1 {
			t.Fatalf("expected 1 active doc, got %d", len(docs))
		}

		// Bypass the Go struct entirely — read the raw persisted map.
		raw := docs[0].Data()

		// Documented schema field names (schemas/ips.schema.json) must
		// actually be present in what's stored.
		expectedFields := []string{
			"ips_id", "user_id", "version", "status", "effective_date",
			"risk_tolerance", "time_horizon_years", "target_allocation",
			"constraints", "created_at",
		}
		for _, field := range expectedFields {
			if _, ok := raw[field]; !ok {
				t.Errorf("expected persisted document to contain field %q, but it was missing. raw keys: %v", field, raw)
			}
		}

		// Go's default PascalCase field names must NOT be present — this
		// is the specific regression the firestore struct tags fix guards
		// against. If this ever fails, someone removed a `firestore:` tag.
		unexpectedFields := []string{"IPSID", "UserID", "Status", "RiskTolerance", "TargetAllocation"}
		for _, field := range unexpectedFields {
			if _, ok := raw[field]; ok {
				t.Errorf("persisted document contains Go field name %q instead of the documented schema name — firestore struct tags regression", field)
			}
		}
	})

	t.Run("revision (supersede old, create new)", func(t *testing.T) {
		newIPS := baseIPS(2)
		err := c.UpdateIPS(ctx, newIPS)
		if err != nil {
			t.Fatalf("expected no error, got: %v", err)
		}

		// Verify new document is active
		docs, err := c.fs.Collection(collectionIPS).Where("ips_id", "==", "userA_ips").Where("status", "==", contracts.IPSStatusActive).Documents(ctx).GetAll()
		if err != nil {
			t.Fatalf("query failed: %v", err)
		}
		if len(docs) != 1 {
			t.Fatalf("expected exactly 1 active doc, got %d", len(docs))
		}

		var activeIPS contracts.InvestmentPolicyStatement
		if err := docs[0].DataTo(&activeIPS); err != nil {
			t.Fatalf("failed to decode: %v", err)
		}
		if activeIPS.Version != 2 {
			t.Fatalf("expected version 2 to be active, got %d", activeIPS.Version)
		}

		// Verify old document is superseded
		oldDoc, err := c.fs.Collection(collectionIPS).Doc("userA_ips_v1").Get(ctx)
		if err != nil {
			t.Fatalf("failed to get old doc: %v", err)
		}
		var oldIPS contracts.InvestmentPolicyStatement
		if err := oldDoc.DataTo(&oldIPS); err != nil {
			t.Fatalf("failed to decode old doc: %v", err)
		}
		if oldIPS.Status != contracts.IPSStatusSuperseded {
			t.Fatalf("expected status superseded, got %s", oldIPS.Status)
		}
		if oldIPS.SupersededBy == nil || *oldIPS.SupersededBy != "userA_ips_v2" {
			if oldIPS.SupersededBy == nil {
				t.Fatalf("expected superseded by userA_ips_v2, got nil")
			} else {
				t.Fatalf("expected superseded by userA_ips_v2, got %v", *oldIPS.SupersededBy)
			}
		}
	})

	t.Run("fails on non-active status", func(t *testing.T) {
		ips := baseIPS(3)
		ips.Status = contracts.IPSStatusDraft // Should fail, must be "active"
		err := c.UpdateIPS(ctx, ips)
		if err == nil {
			t.Fatalf("expected error due to non-active status")
		}
	})

	t.Run("fails schema validation", func(t *testing.T) {
		ips := baseIPS(3)
		ips.RiskTolerance = "crazy" // Invalid
		err := c.UpdateIPS(ctx, ips)
		if err == nil {
			t.Fatalf("expected error due to schema validation")
		}
	})
}
