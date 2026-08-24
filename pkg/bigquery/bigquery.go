package bigquery

import (
	"fmt"
	"regexp"
	"strings"
)

// MaxBytesBilled is the maximum number of bytes allowed to be billed for a BigQuery job.
// This is to prevent full table scans on large tables. (10 MB)
const MaxBytesBilled = 10 * 1024 * 1024

var (
	blockCommentRegex               = regexp.MustCompile(`/\*[\s\S]*?\*/`)
	lineCommentRegex                = regexp.MustCompile(`(--|#)[^\n]*`)
	selectStartRegex                = regexp.MustCompile(`(?i)^SELECT\b`)
	transactionTableRegex           = regexp.MustCompile(`(?i)\b([a-zA-Z0-9_]+_transactions)\b`)
	qualifiedTransactionRefBacktick = regexp.MustCompile("`[^`]*\\b([a-zA-Z0-9_]+_transactions)`")
	qualifiedTransactionRefBare     = regexp.MustCompile(`(?i)\b(?:[A-Za-z_][\w-]*\.)+([a-zA-Z0-9_]+_transactions)\b`)
	limitRegex                      = regexp.MustCompile(`(?i)\blimit\s+\d+\s*;?\s*$`)
	restrictedRegex                 = regexp.MustCompile(`(?i)\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|MERGE|EXPORT|LOAD|CALL|EXECUTE)\b`)
	validUserIDRegex                = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,64}$`)
)

// ValidateUserID verifies that a user_id conforms to the safe identifier format ^[a-zA-Z0-9_-]{1,64}$.
func ValidateUserID(userID string) error {
	trimmed := strings.TrimSpace(userID)
	if trimmed == "" || !validUserIDRegex.MatchString(trimmed) {
		return fmt.Errorf("invalid user_id format: %q", userID)
	}
	return nil
}

func stripCommentsAndSpace(sql string) string {
	cleaned := blockCommentRegex.ReplaceAllString(sql, " ")
	cleaned = lineCommentRegex.ReplaceAllString(cleaned, " ")
	return strings.TrimSpace(cleaned)
}

// PrepareSecureSQL takes a generated SQL query and a user ID, and returns a secure,
// row-scoped version of the query along with a map of parameters.
// This enforces the read-only, table targeting, user scoping, and LIMIT constraints.
func PrepareSecureSQL(generatedSQL, userID string) (string, map[string]interface{}, error) {
	if err := ValidateUserID(userID); err != nil {
		return "", nil, err
	}
	trimmed := stripCommentsAndSpace(generatedSQL)
	if trimmed == "" {
		return "", nil, fmt.Errorf("query cannot be empty")
	}

	// 1. Whitelist: Must start with SELECT
	if !selectStartRegex.MatchString(trimmed) {
		return "", nil, fmt.Errorf("read-only queries only: only SELECT queries are allowed")
	}

	// 2. Disallow multi-statement queries
	// Trim any trailing semicolon, then check if any internal semicolons exist
	hadTrailingSemicolon := strings.HasSuffix(strings.TrimSpace(trimmed), ";")
	sqlWithoutTrailingSemicolon := strings.TrimRight(trimmed, "; \t\n")
	if strings.Contains(sqlWithoutTrailingSemicolon, ";") {
		return "", nil, fmt.Errorf("multi-statement queries are not permitted")
	}

	// 3. Reject any restricted write/DDL/execution keywords anywhere in query
	if match := restrictedRegex.FindString(sqlWithoutTrailingSemicolon); match != "" {
		return "", nil, fmt.Errorf("read-only queries only: %s is not allowed", strings.ToUpper(match))
	}

	// 4. Target checking: Must target a transactions table (e.g. checking_transactions)
	tableMatch := transactionTableRegex.FindStringSubmatch(sqlWithoutTrailingSemicolon)
	if len(tableMatch) < 2 {
		return "", nil, fmt.Errorf("query must target a transactions table (e.g. checking_transactions)")
	}
	targetTable := strings.ToLower(tableMatch[1])

	// 5. CTE-based row-level user scoping.
	// Strip ANY qualifier prefix from the transactions table so the CTE below shadows
	// every reference. BigQuery CTEs only shadow unqualified names — a query using
	// `project.dataset.checking_transactions` would otherwise skip user_id scoping.
	cleanUserSQL := qualifiedTransactionRefBacktick.ReplaceAllString(sqlWithoutTrailingSemicolon, "$1")
	cleanUserSQL = qualifiedTransactionRefBare.ReplaceAllString(cleanUserSQL, "$1")

	// 6. Ensure LIMIT safeguard
	if !limitRegex.MatchString(cleanUserSQL) {
		if hadTrailingSemicolon {
			cleanUserSQL = cleanUserSQL + " LIMIT 100;"
		} else {
			cleanUserSQL = cleanUserSQL + " LIMIT 100"
		}
	} else if hadTrailingSemicolon && !strings.HasSuffix(cleanUserSQL, ";") {
		cleanUserSQL = cleanUserSQL + ";"
	}

	secureSQL := fmt.Sprintf("WITH %s AS (\n  SELECT * FROM portfolio_copilot.%s WHERE user_id = @user_id\n)\n%s", targetTable, targetTable, cleanUserSQL)

	params := map[string]interface{}{
		"user_id": userID,
	}

	return secureSQL, params, nil
}
