package documentai

import (
	"context"
	"errors"
	"testing"

	"portfolio-copilot/pkg/contracts"
)

func TestMaskSSN(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"123-45-6789", "***-**-6789"},
		{"987654321", "***-**-4321"},
		{"4321", "***-**-4321"},
		{"", ""},
	}

	for _, tt := range tests {
		got := MaskSSN(tt.input)
		if got != tt.want {
			t.Errorf("MaskSSN(%q) = %q, want %q", tt.input, got, tt.want)
		}
	}
}

func TestParseCurrency(t *testing.T) {
	tests := []struct {
		input string
		want  float64
	}{
		{"$125,000.50", 125000.50},
		{"220000.00", 220000.00},
		{" -500.25 ", -500.25},
		{"invalid", 0.0},
		{"", 0.0},
	}

	for _, tt := range tests {
		got := ParseCurrency(tt.input)
		if got != tt.want {
			t.Errorf("ParseCurrency(%q) = %v, want %v", tt.input, got, tt.want)
		}
	}
}

func TestParseTaxYear(t *testing.T) {
	tests := []struct {
		val         string
		defaultYear int
		want        int
	}{
		{"w2_2023_statement.pdf", 2024, 2023},
		{"form_w2_2024.png", 2025, 2024},
		{"random_doc.pdf", 2023, 2023},
		{"random_doc.pdf", 1800, 2024},
	}

	for _, tt := range tests {
		got := ParseTaxYear(tt.val, tt.defaultYear)
		if got != tt.want {
			t.Errorf("ParseTaxYear(%q, %d) = %d, want %d", tt.val, tt.defaultYear, got, tt.want)
		}
	}
}

func TestMockW2Parser_Success(t *testing.T) {
	parser := NewMockW2Parser()
	ctx := context.Background()
	dummyBytes := []byte("%PDF-1.4 dummy content")

	doc, err := parser.ParseW2(ctx, dummyBytes, "application/pdf", "W2_2024.pdf", "user_123")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if doc.UserID != "user_123" {
		t.Errorf("expected UserID user_123, got %s", doc.UserID)
	}
	if doc.TaxYear != 2024 {
		t.Errorf("expected TaxYear 2024, got %d", doc.TaxYear)
	}
	if doc.WagesAndCompensation.Box1WagesTipsOtherCompUSD != 220000.0 {
		t.Errorf("expected Box 1 wages 220000.0, got %v", doc.WagesAndCompensation.Box1WagesTipsOtherCompUSD)
	}
	if doc.Employee.SSNMasked != "***-**-4589" {
		t.Errorf("expected masked SSN, got %s", doc.Employee.SSNMasked)
	}
	if !doc.Validate() {
		t.Errorf("expected valid W2Document")
	}
}

func TestMockW2Parser_Errors(t *testing.T) {
	parser := NewMockW2Parser()
	ctx := context.Background()

	// Empty bytes
	_, err := parser.ParseW2(ctx, []byte{}, "application/pdf", "W2.pdf", "user_123")
	if err == nil {
		t.Errorf("expected error for empty file bytes")
	}

	// Custom failure
	parser.FailErr = errors.New("simulated error")
	_, err = parser.ParseW2(ctx, []byte("data"), "application/pdf", "W2.pdf", "user_123")
	if err == nil || err.Error() != "simulated error" {
		t.Errorf("expected simulated error, got %v", err)
	}

	// Custom W2
	customDoc := &contracts.W2Document{
		ID:      "w2-custom-1",
		TaxYear: 2023,
		WagesAndCompensation: contracts.W2Wages{
			Box1WagesTipsOtherCompUSD: 180000.0,
		},
	}
	parser.FailErr = nil
	parser.CustomW2 = customDoc
	doc, err := parser.ParseW2(ctx, []byte("data"), "application/pdf", "custom_w2.pdf", "custom_user")
	if err != nil || doc == nil || doc.UserID != "custom_user" || doc.WagesAndCompensation.Box1WagesTipsOtherCompUSD != 180000.0 {
		t.Errorf("failed custom W2 test: doc = %+v, err = %v", doc, err)
	}
}

func TestIsAffirmative(t *testing.T) {
	affirmative := []string{"true", "yes", "x", "1", "checked", "YES", "True"}
	for _, a := range affirmative {
		if !isAffirmative(a) {
			t.Errorf("expected isAffirmative(%q) = true", a)
		}
	}
	negative := []string{"false", "no", "0", "", "unchecked"}
	for _, n := range negative {
		if isAffirmative(n) {
			t.Errorf("expected isAffirmative(%q) = false", n)
		}
	}
}

