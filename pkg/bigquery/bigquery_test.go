package bigquery

import (
	"strings"
	"testing"
)

func TestPrepareSecureSQL(t *testing.T) {
	userID := "user-123"

	tests := []struct {
		name          string
		generatedSQL  string
		expectError   bool
		expectedError string
		checkQuery    func(t *testing.T, secureSQL string, params map[string]interface{})
	}{
		{
			name:         "Basic valid query",
			generatedSQL: "SELECT * FROM chase_transactions",
			expectError:  false,
			checkQuery: func(t *testing.T, secureSQL string, params map[string]interface{}) {
				if !strings.Contains(secureSQL, "portfolio_copilot.chase_transactions") {
					t.Errorf("Expected scoped table name in query, got: %s", secureSQL)
				}
				if !strings.Contains(secureSQL, "user_id = @user_id") {
					t.Errorf("Expected user_id parameter in query, got: %s", secureSQL)
				}
				if !strings.HasSuffix(secureSQL, "LIMIT 100") {
					t.Errorf("Expected LIMIT 100 at the end, got: %s", secureSQL)
				}
				if params["user_id"] != userID {
					t.Errorf("Expected user_id parameter to be %s, got: %v", userID, params["user_id"])
				}
			},
		},
		{
			name:         "Query with existing LIMIT",
			generatedSQL: "SELECT category, SUM(amount) FROM chase_transactions GROUP BY category LIMIT 10",
			expectError:  false,
			checkQuery: func(t *testing.T, secureSQL string, params map[string]interface{}) {
				if strings.Contains(secureSQL, "LIMIT 100") {
					t.Errorf("Did not expect LIMIT 100 when query already has LIMIT, got: %s", secureSQL)
				}
			},
		},
		{
			name:          "Write query rejected",
			generatedSQL:  "DELETE FROM chase_transactions WHERE amount > 100",
			expectError:   true,
			expectedError: "read-only queries only: DELETE is not allowed",
		},
		{
			name:          "Missing table target",
			generatedSQL:  "SELECT * FROM some_other_table",
			expectError:   true,
			expectedError: "query must target chase_transactions table",
		},
		{
			name:         "Valid query with UPDATE in column name",
			generatedSQL: "SELECT update_date FROM chase_transactions",
			expectError:  false,
			checkQuery: func(t *testing.T, secureSQL string, params map[string]interface{}) {
				if !strings.Contains(secureSQL, "update_date") {
					t.Errorf("Expected column update_date to be preserved, got: %s", secureSQL)
				}
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			secureSQL, params, err := PrepareSecureSQL(tt.generatedSQL, userID)

			if (err != nil) != tt.expectError {
				t.Fatalf("Expected error: %v, got: %v", tt.expectError, err)
			}

			if tt.expectError && err != nil {
				if !strings.Contains(err.Error(), tt.expectedError) {
					t.Errorf("Expected error containing %q, got %q", tt.expectedError, err.Error())
				}
				return
			}

			if tt.checkQuery != nil {
				tt.checkQuery(t, secureSQL, params)
			}
		})
	}
}
