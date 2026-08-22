package documentai

import (
	"context"
	"fmt"
	"time"

	"portfolio-copilot/pkg/contracts"
)

// MockW2Parser implements Parser for deterministic local development and automated CI tests.
type MockW2Parser struct {
	CustomW2 *contracts.W2Document
	FailErr  error
}

// NewMockW2Parser returns a new MockW2Parser instance.
func NewMockW2Parser() *MockW2Parser {
	return &MockW2Parser{}
}

// ParseW2 returns a deterministic parsed W-2 document.
func (m *MockW2Parser) ParseW2(ctx context.Context, fileBytes []byte, mimeType string, filename string, userID string) (*contracts.W2Document, error) {
	if m.FailErr != nil {
		return nil, m.FailErr
	}
	if len(fileBytes) == 0 {
		return nil, fmt.Errorf("empty document payload")
	}

	if m.CustomW2 != nil {
		w2 := *m.CustomW2
		w2.UserID = userID
		w2.Filename = filename
		w2.SizeBytes = int64(len(fileBytes))
		return &w2, nil
	}

	nowStr := time.Now().UTC().Format(time.RFC3339)
	docID := fmt.Sprintf("w2-%d", time.Now().UnixNano())
	taxYear := ParseTaxYear(filename, 2024)

	fedTax := 38450.0
	ssWages := 168600.0
	ssTax := 10453.20
	medWages := 220000.0
	medTax := 3190.0
	conf := 0.98

	return &contracts.W2Document{
		ID:              docID,
		UserID:          userID,
		TaxYear:         taxYear,
		Filename:        filename,
		SizeBytes:       int64(len(fileBytes)),
		UploadedAt:      nowStr,
		ParsedAt:        nowStr,
		ConfidenceScore: &conf,
		Status:          contracts.W2StatusSuccess,
		Employer: &contracts.W2Employer{
			Name:    "Alphabet Inc.",
			EIN:     "94-3289634",
			Address: "1600 Amphitheatre Pkwy, Mountain View, CA 94043",
		},
		Employee: &contracts.W2Employee{
			Name:      "Alex Mercer",
			SSNMasked: "***-**-4589",
			Address:   "742 Evergreen Terrace, Springfield, OR 97477",
		},
		WagesAndCompensation: contracts.W2Wages{
			Box1WagesTipsOtherCompUSD: 220000.0,
			Box2FederalIncomeTaxUSD:   &fedTax,
			Box3SocialSecurityWagesUSD: &ssWages,
			Box4SocialSecurityTaxUSD:   &ssTax,
			Box5MedicareWagesTipsUSD:   &medWages,
			Box6MedicareTaxWithheldUSD: &medTax,
		},
		Box12Items: []contracts.W2Box12Item{
			{Code: "D", Description: "401(k) elective deferral", AmountUSD: 23000.0},
			{Code: "W", Description: "Employer HSA contribution", AmountUSD: 4150.0},
		},
		Box13Checkboxes: &contracts.W2Box13Checkboxes{
			RetirementPlan: true,
		},
		Box14Other: []contracts.W2OtherItem{
			{Label: "CA SDI", AmountUSD: 1378.48},
		},
		StateTaxes: []contracts.W2StateTax{
			{State: "CA", EmployerStateID: "123-4567-8", StateWagesUSD: 220000.0, StateIncomeTaxUSD: 18250.0},
		},
		LocalTaxes: []contracts.W2LocalTax{
			{LocalityName: "San Francisco", LocalWagesUSD: 220000.0, LocalIncomeTaxUSD: 0.0},
		},
		RawEntities: map[string]string{
			"w2_box1_wages": "220000.00",
			"w2_box2_tax":   "38450.00",
			"employer_name": "Alphabet Inc.",
		},
	}, nil
}
