package contracts_test

import (
	"encoding/json"
	"testing"

	"portfolio-copilot/pkg/contracts"
)

func TestUserProfileRoundTrip(t *testing.T) {
	profile := contracts.UserProfile{
		UserID:                  "demo_user",
		FullName:                "Alex Mercer",
		Email:                   "alex.mercer@example.com",
		DateOfBirth:             "1980-06-15",
		Age:                     46,
		MaritalStatus:           "married",
		DependentsCount:         2,
		FamilyMembers: []contracts.FamilyMember{
			{Name: "Sarah Mercer", Relationship: "spouse", Age: 44},
			{Name: "Leo Mercer", Relationship: "child", Age: 12},
		},
		EmploymentStatus:        "employed",
		Occupation:              "Staff Systems Engineer",
		AnnualIncomeUSD:         220000,
		TargetRetirementAge:     61,
		MonthlyHousingPaymentUSD: 4200,
		RiskToleranceNotes:      "Moderate volatility comfort.",
		FinancialGoalsNotes:     "Early retirement by 2041.",
		UpdatedAt:               "2026-08-01T00:00:00Z",
	}

	data, err := json.Marshal(profile)
	if err != nil {
		t.Fatalf("failed to marshal UserProfile: %v", err)
	}

	var decoded contracts.UserProfile
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("failed to unmarshal UserProfile: %v", err)
	}

	if decoded.UserID != profile.UserID || decoded.FullName != profile.FullName {
		t.Errorf("decoded profile mismatch: got %+v, want %+v", decoded, profile)
	}
	if len(decoded.FamilyMembers) != 2 {
		t.Errorf("expected 2 family members, got %d", len(decoded.FamilyMembers))
	}
}
