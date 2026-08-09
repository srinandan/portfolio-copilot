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
	blockCommentRegex = regexp.MustCompile(`/\*[\s\S]*?\*/`)
	lineCommentRegex  = regexp.MustCompile(`(--|#)[^\n]*`)
	selectStartRegex  = regexp.MustCompile(`(?i)^SELECT\b`)
	chaseTableRegex   = regexp.MustCompile(`(?i)\bchase_transactions\b`)
	portfolioTableRef = regexp.MustCompile(`(?i)\bportfolio_copilot\.chase_transactions\b`)
	limitRegex        = regexp.MustCompile(`(?i)\blimit\s+\d+\s*;?\s*$`)
	restrictedRegex   = regexp.MustCompile(`(?i)\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|MERGE|EXPORT|LOAD|CALL|EXECUTE)\b`)
)

func stripCommentsAndSpace(sql string) string {
	cleaned := blockCommentRegex.ReplaceAllString(sql, " ")
	cleaned = lineCommentRegex.ReplaceAllString(cleaned, " ")
	return strings.TrimSpace(cleaned)
}

// PrepareSecureSQL takes a generated SQL query and a user ID, and returns a secure,
// row-scoped version of the query along with a map of parameters.
// This enforces the read-only, table targeting, user scoping, and LIMIT constraints.
func PrepareSecureSQL(generatedSQL, userID string) (string, map[string]interface{}, error) {
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

	// 4. Target checking: Must target chase_transactions
	if !chaseTableRegex.MatchString(sqlWithoutTrailingSemicolon) {
		return "", nil, fmt.Errorf("query must target chase_transactions table")
	}

	// 5. CTE-based row-level user scoping
	// Shadow the chase_transactions table inside a CTE scoped to @user_id
	cleanUserSQL := portfolioTableRef.ReplaceAllString(sqlWithoutTrailingSemicolon, "chase_transactions")

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

	secureSQL := fmt.Sprintf("WITH chase_transactions AS (\n  SELECT * FROM portfolio_copilot.chase_transactions WHERE user_id = @user_id\n)\n%s", cleanUserSQL)

	params := map[string]interface{}{
		"user_id": userID,
	}

	return secureSQL, params, nil
}
