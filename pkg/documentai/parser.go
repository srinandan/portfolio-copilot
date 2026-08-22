package documentai

import (
	"context"
	"regexp"
	"strconv"
	"strings"

	"portfolio-copilot/pkg/contracts"
)

// Parser defines the interface for extracting structured W-2 data from document files.
type Parser interface {
	ParseW2(ctx context.Context, fileBytes []byte, mimeType string, filename string, userID string) (*contracts.W2Document, error)
}

var ssnRegex = regexp.MustCompile(`\b\d{3}-\d{2}-(\d{4})\b`)
var numericCleanRegex = regexp.MustCompile(`[^0-9.-]`)

// MaskSSN replaces the first 5 digits of an SSN with asterisks, preserving the last 4 digits.
func MaskSSN(ssn string) string {
	clean := strings.TrimSpace(ssn)
	if clean == "" {
		return ""
	}
	// Match standard format 123-45-6789
	if ssnRegex.MatchString(clean) {
		return ssnRegex.ReplaceAllString(clean, "***-**-$1")
	}
	// Match 9 unformatted digits
	digits := regexp.MustCompile(`\D`).ReplaceAllString(clean, "")
	if len(digits) == 9 {
		return "***-**-" + digits[5:]
	}
	if len(digits) >= 4 {
		return "***-**-" + digits[len(digits)-4:]
	}
	return "***-**-****"
}

// ParseCurrency parses a string amount into float64, stripping currency symbols and commas.
func ParseCurrency(val string) float64 {
	clean := strings.TrimSpace(val)
	if clean == "" {
		return 0.0
	}
	cleaned := numericCleanRegex.ReplaceAllString(clean, "")
	amt, err := strconv.ParseFloat(cleaned, 64)
	if err != nil {
		return 0.0
	}
	return amt
}

// ParseTaxYear attempts to parse a 4-digit tax year from a string.
func ParseTaxYear(val string, defaultYear int) int {
	yearRegex := regexp.MustCompile(`(?:^|[^0-9])(19\d{2}|20\d{2})(?:[^0-9]|$)`)
	matches := yearRegex.FindStringSubmatch(val)
	if len(matches) >= 2 && matches[1] != "" {
		if year, err := strconv.Atoi(matches[1]); err == nil && year >= 1990 && year <= 2100 {
			return year
		}
	}
	if defaultYear >= 1990 && defaultYear <= 2100 {
		return defaultYear
	}
	return 2024
}
