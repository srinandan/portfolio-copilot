package bigquery

import (
	"fmt"
	"regexp"
	"strings"
)

// MaxBytesBilled is the maximum number of bytes allowed to be billed for a BigQuery job.
// This is to prevent full table scans on large tables. (10 MB)
const MaxBytesBilled = 10 * 1024 * 1024

// PrepareSecureSQL takes a generated SQL query and a user ID, and returns a secure,
// row-scoped version of the query along with a map of parameters.
// This enforces the read-only, table targeting, user scoping, and LIMIT constraints.
func PrepareSecureSQL(generatedSQL, userID string) (string, map[string]interface{}, error) {
	// 1. Check for write operations to prevent them
	for _, restricted := range []string{"INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"} {
		// Use word boundaries to prevent matching columns like update_date
		re := regexp.MustCompile(fmt.Sprintf(`(?i)\b%s\b`, restricted))
		if re.MatchString(generatedSQL) {
			return "", nil, fmt.Errorf("read-only queries only: %s is not allowed", restricted)
		}
	}

	// 2. Target checking and row-level scoping
	re := regexp.MustCompile(`(?i)\bchase_transactions\b`)
	if !re.MatchString(generatedSQL) {
		return "", nil, fmt.Errorf("query must target chase_transactions table")
	}

	scopedTable := "(SELECT * FROM portfolio_copilot.chase_transactions WHERE user_id = @user_id)"
	secureSQL := re.ReplaceAllString(generatedSQL, scopedTable)

	// 3. Ensure LIMIT safeguard
	// Use regex to properly check for an outer limit, not just any "LIMIT" in the string
	hasLimit := false
	limitRegex := regexp.MustCompile(`(?i)\blimit\s+\d+\s*;?\s*$`)

	if limitRegex.MatchString(secureSQL) {
		hasLimit = true
	}

	if !hasLimit {
		secureSQL = strings.TrimSpace(secureSQL)
		// Handle semicolon properly
		if strings.HasSuffix(secureSQL, ";") {
			secureSQL = strings.TrimSuffix(secureSQL, ";")
			secureSQL = strings.TrimSpace(secureSQL) + " LIMIT 100;"
		} else {
			secureSQL = secureSQL + " LIMIT 100"
		}
	}

	params := map[string]interface{}{
		"user_id": userID,
	}

	return secureSQL, params, nil
}
