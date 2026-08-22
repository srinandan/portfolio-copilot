package contracts

import (
	"encoding/json"
	"testing"
)

func TestW2Document_JSONRoundtrip(t *testing.T) {
	fedTax := 35000.0
	ssWages := 160200.0
	ssTax := 9932.40
	medWages := 220000.0
	medTax := 3190.0
	conf := 0.98

	w2 := W2Document{
		ID:         "w2-2024-test-1",
		UserID:     "user-123",
		TaxYear:    2024,
		DocumentID: "doc-999",
		Filename:   "w2_2024.pdf",
		SizeBytes:  102400,
		UploadedAt: "2026-08-01T12:00:00Z",
		ParsedAt:   "2026-08-01T12:00:05Z",
		ConfidenceScore: &conf,
		Status:     W2StatusSuccess,
		Employer: &W2Employer{
			Name:    "Acme Corporation",
			EIN:     "12-3456789",
			Address: "500 Roadrunner Way, San Jose, CA 95110",
		},
		Employee: &W2Employee{
			Name:      "Alex Mercer",
			SSNMasked: "***-**-1234",
			Address:   "123 Main St, San Francisco, CA 94105",
		},
		WagesAndCompensation: W2Wages{
			Box1WagesTipsOtherCompUSD: 220000.0,
			Box2FederalIncomeTaxUSD:   &fedTax,
			Box3SocialSecurityWagesUSD: &ssWages,
			Box4SocialSecurityTaxUSD:   &ssTax,
			Box5MedicareWagesTipsUSD:   &medWages,
			Box6MedicareTaxWithheldUSD: &medTax,
		},
		Box12Items: []W2Box12Item{
			{Code: "D", Description: "401(k) elective deferral", AmountUSD: 23000.0},
			{Code: "W", Description: "Employer HSA contribution", AmountUSD: 4150.0},
		},
		Box13Checkboxes: &W2Box13Checkboxes{
			RetirementPlan: true,
		},
		Box14Other: []W2OtherItem{
			{Label: "CA SDI", AmountUSD: 1378.48},
		},
		StateTaxes: []W2StateTax{
			{State: "CA", EmployerStateID: "999-888-7", StateWagesUSD: 220000.0, StateIncomeTaxUSD: 18500.0},
		},
		LocalTaxes: []W2LocalTax{
			{LocalityName: "San Francisco", LocalWagesUSD: 220000.0, LocalIncomeTaxUSD: 0.0},
		},
		RawEntities: map[string]string{
			"w2_box1": "220000.00",
		},
	}

	data, err := json.Marshal(w2)
	if err != nil {
		t.Fatalf("failed to marshal W2Document: %v", err)
	}

	var parsed W2Document
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatalf("failed to unmarshal W2Document: %v", err)
	}

	if parsed.ID != w2.ID || parsed.UserID != w2.UserID || parsed.TaxYear != 2024 {
		t.Errorf("mismatched top level fields: got %+v, want %+v", parsed, w2)
	}
	if parsed.WagesAndCompensation.Box1WagesTipsOtherCompUSD != 220000.0 {
		t.Errorf("mismatched box 1 wages: got %v", parsed.WagesAndCompensation.Box1WagesTipsOtherCompUSD)
	}
	if len(parsed.Box12Items) != 2 || parsed.Box12Items[0].Code != "D" {
		t.Errorf("mismatched box 12 items: got %+v", parsed.Box12Items)
	}
	if !parsed.Validate() {
		t.Errorf("expected valid W2Document")
	}
}

func TestW2Document_ValidateEdgeCases(t *testing.T) {
	tests := []struct {
		name  string
		doc   W2Document
		valid bool
	}{
		{
			name: "valid minimal",
			doc: W2Document{
				ID:         "w2-1",
				UserID:     "user-1",
				TaxYear:    2024,
				UploadedAt: "2026-01-01T00:00:00Z",
				Status:     W2StatusSuccess,
				WagesAndCompensation: W2Wages{
					Box1WagesTipsOtherCompUSD: 100000.0,
				},
			},
			valid: true,
		},
		{
			name: "missing ID",
			doc: W2Document{
				UserID:     "user-1",
				TaxYear:    2024,
				UploadedAt: "2026-01-01T00:00:00Z",
				Status:     W2StatusSuccess,
				WagesAndCompensation: W2Wages{
					Box1WagesTipsOtherCompUSD: 100000.0,
				},
			},
			valid: false,
		},
		{
			name: "invalid tax year",
			doc: W2Document{
				ID:         "w2-1",
				UserID:     "user-1",
				TaxYear:    1800,
				UploadedAt: "2026-01-01T00:00:00Z",
				Status:     W2StatusSuccess,
				WagesAndCompensation: W2Wages{
					Box1WagesTipsOtherCompUSD: 100000.0,
				},
			},
			valid: false,
		},
		{
			name: "negative wages",
			doc: W2Document{
				ID:         "w2-1",
				UserID:     "user-1",
				TaxYear:    2024,
				UploadedAt: "2026-01-01T00:00:00Z",
				Status:     W2StatusSuccess,
				WagesAndCompensation: W2Wages{
					Box1WagesTipsOtherCompUSD: -500.0,
				},
			},
			valid: false,
		},
		{
			name: "invalid status",
			doc: W2Document{
				ID:         "w2-1",
				UserID:     "user-1",
				TaxYear:    2024,
				UploadedAt: "2026-01-01T00:00:00Z",
				Status:     "UNKNOWN",
				WagesAndCompensation: W2Wages{
					Box1WagesTipsOtherCompUSD: 100000.0,
				},
			},
			valid: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.doc.Validate(); got != tt.valid {
				t.Errorf("Validate() = %v, want %v", got, tt.valid)
			}
		})
	}
}
