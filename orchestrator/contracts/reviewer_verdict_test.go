package contracts_test

import (
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"portfolio-copilot/orchestrator/contracts"
)

func TestReviewerVerdictRoundTripAndValidation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)

	tests := []struct {
		name          string
		input         contracts.ReviewerVerdict
		expectedValid bool
	}{
		{
			name: "Valid ReviewerVerdict (Passed)",
			input: contracts.ReviewerVerdict{
				VerdictID: "verdict_333",
				ActionID:  "action_777",
				IPSVersionCheckedAgainst: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				RuleResults: []contracts.RuleResult{
					{
						RuleID:      "excluded-ticker",
						Description: "Check ticker is not in excluded_tickers list.",
						Passed:      true,
					},
				},
				OverallPass:           true,
				RequiresHumanApproval: true,
				ReviewerSkillVersion: contracts.SkillVersionRef{
					SkillName:    "reviewer-critic",
					SkillVersion: "1.0.0",
				},
				ReviewedAt: now,
			},
			expectedValid: true,
		},
		{
			name: "Valid ReviewerVerdict (Rejection/Failed rule path)",
			input: contracts.ReviewerVerdict{
				VerdictID: "verdict_444",
				ActionID:  "action_777",
				IPSVersionCheckedAgainst: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				RuleResults: []contracts.RuleResult{
					{
						RuleID:      "concentration-limit",
						Description: "Position exceeds 15% limit",
						Passed:      false,
						Detail:      ptrString("Proposed action results in 22% allocation to TSLA"),
					},
				},
				OverallPass:           false,
				RequiresHumanApproval: true,
				ReviewerSkillVersion: contracts.SkillVersionRef{
					SkillName:    "reviewer-critic",
					SkillVersion: "1.0.0",
				},
				ReviewedAt: now,
			},
			expectedValid: true,
		},
		{
			name: "Missing Verdict ID (invalid)",
			input: contracts.ReviewerVerdict{
				VerdictID:  "",
				ActionID:   "action_777",
				ReviewedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "Missing IPSVersionCheckedAgainst (invalid)",
			input: contracts.ReviewerVerdict{
				VerdictID: "verdict_333",
				ActionID:  "action_777",
				IPSVersionCheckedAgainst: contracts.IPSVersionRef{
					IPSID:   "",
					Version: 0,
				},
				RuleResults: []contracts.RuleResult{
					{RuleID: "excluded-ticker", Description: "Check excluded", Passed: true},
				},
				ReviewerSkillVersion: contracts.SkillVersionRef{
					SkillName:    "reviewer",
					SkillVersion: "1.0",
				},
				ReviewedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "Missing ReviewerSkillVersion (invalid)",
			input: contracts.ReviewerVerdict{
				VerdictID: "verdict_333",
				ActionID:  "action_777",
				IPSVersionCheckedAgainst: contracts.IPSVersionRef{
					IPSID:   "ips_1",
					Version: 1,
				},
				RuleResults: []contracts.RuleResult{
					{RuleID: "excluded-ticker", Description: "Check excluded", Passed: true},
				},
				ReviewerSkillVersion: contracts.SkillVersionRef{
					SkillName:    "",
					SkillVersion: "",
				},
				ReviewedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "Zero rule results (invalid)",
			input: contracts.ReviewerVerdict{
				VerdictID:   "verdict_333",
				ActionID:    "action_777",
				ReviewedAt:  now,
				RuleResults: []contracts.RuleResult{},
			},
			expectedValid: false,
		},
		{
			name: "Rule with missing rule ID (invalid)",
			input: contracts.ReviewerVerdict{
				VerdictID:  "verdict_333",
				ActionID:   "action_777",
				ReviewedAt: now,
				RuleResults: []contracts.RuleResult{
					{
						RuleID:      "",
						Description: "Descr",
						Passed:      true,
					},
				},
			},
			expectedValid: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if tc.expectedValid {
				data, err := json.Marshal(tc.input)
				if err != nil {
					t.Fatalf("failed to marshal: %v", err)
				}

				var actual contracts.ReviewerVerdict
				if err := json.Unmarshal(data, &actual); err != nil {
					t.Fatalf("failed to unmarshal: %v", err)
				}

				actual.ReviewedAt = actual.ReviewedAt.UTC()

				if !reflect.DeepEqual(tc.input, actual) {
					t.Errorf("round-trip mismatch\nexpected: %+v\ngot: %+v", tc.input, actual)
				}
			}

			if tc.input.Validate() != tc.expectedValid {
				t.Errorf("expected Validate() to be %v, got %v", tc.expectedValid, tc.input.Validate())
			}
		})
	}
}
