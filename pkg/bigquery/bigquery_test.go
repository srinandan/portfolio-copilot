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
			name:         "Valid query with leading comments and trailing semicolon",
			generatedSQL: "-- Calculate total spent\n/* Block comment */\nSELECT category, SUM(amount) FROM chase_transactions GROUP BY category;",
			expectError:  false,
			checkQuery: func(t *testing.T, secureSQL string, params map[string]interface{}) {
				if !strings.HasPrefix(secureSQL, "WITH chase_transactions AS") {
					t.Errorf("Expected CTE prefix, got: %s", secureSQL)
				}
				if !strings.HasSuffix(secureSQL, "LIMIT 100;") {
					t.Errorf("Expected LIMIT 100; at the end, got: %s", secureSQL)
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
			name:          "Write query rejected - DELETE",
			generatedSQL:  "DELETE FROM chase_transactions WHERE amount > 100",
			expectError:   true,
			expectedError: "only SELECT queries are allowed",
		},
		{
			name:          "Write query rejected - MERGE",
			generatedSQL:  "MERGE portfolio_copilot.chase_transactions T USING (SELECT '@attacker' AS user_id) S ON TRUE WHEN MATCHED THEN UPDATE SET T.user_id = S.user_id",
			expectError:   true,
			expectedError: "only SELECT queries are allowed",
		},
		{
			name:          "Write query rejected - EXPORT DATA",
			generatedSQL:  "EXPORT DATA OPTIONS(uri='gs://bucket/*.csv', format='CSV') AS SELECT * FROM chase_transactions",
			expectError:   true,
			expectedError: "only SELECT queries are allowed",
		},
		{
			name:          "Write query rejected - LOAD DATA",
			generatedSQL:  "LOAD DATA INTO chase_transactions FROM FILES(format='CSV', uris=['gs://bucket/data.csv'])",
			expectError:   true,
			expectedError: "only SELECT queries are allowed",
		},
		{
			name:          "Write query rejected - EXECUTE IMMEDIATE",
			generatedSQL:  "EXECUTE IMMEDIATE 'INSERT INTO chase_transactions VALUES (1, 2)'",
			expectError:   true,
			expectedError: "only SELECT queries are allowed",
		},
		{
			name:          "Write query rejected - CALL procedure",
			generatedSQL:  "CALL my_dataset.my_procedure()",
			expectError:   true,
			expectedError: "only SELECT queries are allowed",
		},
		{
			name:          "Multi-statement query rejected",
			generatedSQL:  "SELECT * FROM chase_transactions; DROP TABLE chase_transactions;",
			expectError:   true,
			expectedError: "multi-statement queries are not permitted",
		},
		{
			name:          "Empty query rejected",
			generatedSQL:  "   -- only comments\n/* nothing */  ",
			expectError:   true,
			expectedError: "query cannot be empty",
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
		{
			name:         "Query targeting full path portfolio_copilot.chase_transactions is rewritten to CTE",
			generatedSQL: "SELECT * FROM portfolio_copilot.chase_transactions WHERE amount > 50",
			expectError:  false,
			checkQuery: func(t *testing.T, secureSQL string, params map[string]interface{}) {
				// The main SELECT after CTE should reference chase_transactions (pointing to the CTE)
				if !strings.Contains(secureSQL, "SELECT * FROM chase_transactions WHERE amount > 50") {
					t.Errorf("Expected main query to reference CTE chase_transactions, got: %s", secureSQL)
				}
			},
		},
		{
			// Regression test: BigQuery CTEs only shadow unqualified names. A query
			// using `otherproj.otherds.chase_transactions` would otherwise skip the
			// user_id scoping entirely.
			name:         "Query with foreign project qualifier is stripped to CTE",
			generatedSQL: "SELECT * FROM `otherproj.otherds.chase_transactions` WHERE amount > 50",
			expectError:  false,
			checkQuery: func(t *testing.T, secureSQL string, params map[string]interface{}) {
				if strings.Contains(secureSQL, "otherproj") || strings.Contains(secureSQL, "otherds") {
					t.Errorf("Expected foreign qualifier stripped, got: %s", secureSQL)
				}
				// Must reference the unqualified name (which is the CTE).
				if !strings.Contains(secureSQL, "FROM chase_transactions WHERE amount > 50") {
					t.Errorf("Expected main query to reference bare chase_transactions, got: %s", secureSQL)
				}
			},
		},
		{
			name:         "Query with bare project.dataset.chase_transactions qualifier is stripped",
			generatedSQL: "SELECT * FROM myproj.myds.chase_transactions WHERE amount > 50",
			expectError:  false,
			checkQuery: func(t *testing.T, secureSQL string, params map[string]interface{}) {
				if strings.Contains(secureSQL, "myproj") || strings.Contains(secureSQL, "myds") {
					t.Errorf("Expected foreign qualifier stripped, got: %s", secureSQL)
				}
				if !strings.Contains(secureSQL, "FROM chase_transactions WHERE amount > 50") {
					t.Errorf("Expected main query to reference bare chase_transactions, got: %s", secureSQL)
				}
			},
		},
		{
			// A join between the scoped CTE and a foreign-qualified copy would
			// otherwise leak all users' data via the second reference.
			name:         "Query joining foreign chase_transactions is stripped so both sides hit CTE",
			generatedSQL: "SELECT c1.amount FROM chase_transactions c1 JOIN `otherproj.otherds.chase_transactions` c2 ON c1.txn_id = c2.txn_id",
			expectError:  false,
			checkQuery: func(t *testing.T, secureSQL string, params map[string]interface{}) {
				if strings.Contains(secureSQL, "otherproj") {
					t.Errorf("Expected foreign qualifier stripped, got: %s", secureSQL)
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
