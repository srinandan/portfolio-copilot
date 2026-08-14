package bigquery

import (
	"strings"
	"testing"
)

// In bigquery_client_test.go, we only test the functionality that doesn't
// require connecting to real BigQuery, since we don't have auth configured.

func TestSecureSQLRegex(t *testing.T) {
	userID := "user-123"

	tests := []struct {
		name         string
		generatedSQL string
		checkQuery   func(t *testing.T, secureSQL string)
	}{
		{
			name:         "Basic valid query",
			generatedSQL: "SELECT * FROM chase_transactions",
			checkQuery: func(t *testing.T, secureSQL string) {
				if !strings.HasSuffix(secureSQL, "LIMIT 100") {
					t.Errorf("Expected LIMIT 100 at the end, got: %s", secureSQL)
				}
			},
		},
		{
			name:         "Query with semicolon",
			generatedSQL: "SELECT * FROM chase_transactions;",
			checkQuery: func(t *testing.T, secureSQL string) {
				if !strings.HasSuffix(secureSQL, "LIMIT 100;") {
					t.Errorf("Expected LIMIT 100; at the end, got: %s", secureSQL)
				}
			},
		},
		{
			name:         "Query with outer LIMIT",
			generatedSQL: "SELECT * FROM chase_transactions LIMIT 50",
			checkQuery: func(t *testing.T, secureSQL string) {
				if strings.Contains(secureSQL, "LIMIT 100") {
					t.Errorf("Did not expect LIMIT 100 when query already has outer LIMIT, got: %s", secureSQL)
				}
			},
		},
		{
			name:         "Query with subquery LIMIT",
			generatedSQL: "SELECT * FROM (SELECT * FROM chase_transactions LIMIT 10) AS sub",
			checkQuery: func(t *testing.T, secureSQL string) {
				if !strings.HasSuffix(secureSQL, "LIMIT 100") {
					t.Errorf("Expected outer LIMIT 100 to be added, got: %s", secureSQL)
				}
			},
		},
		{
			name:         "Query with semicolon and whitespace",
			generatedSQL: "SELECT * FROM chase_transactions ;  ",
			checkQuery: func(t *testing.T, secureSQL string) {
				if !strings.HasSuffix(secureSQL, "LIMIT 100;") {
					t.Errorf("Expected LIMIT 100; at the end, got: %s", secureSQL)
				}
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			secureSQL, _, _ := PrepareSecureSQL(tt.generatedSQL, userID)
			tt.checkQuery(t, secureSQL)
		})
	}
}

func TestInsertTransactions_EmptyRows(t *testing.T) {
	runner := &BigQueryRunner{client: nil}
	err := runner.InsertTransactions(t.Context(), "portfolio_copilot", "checking_transactions", nil)
	if err != nil {
		t.Errorf("expected nil error on empty rows, got: %v", err)
	}
}
