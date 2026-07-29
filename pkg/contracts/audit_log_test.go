package contracts_test

import (
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"portfolio-copilot/pkg/contracts"
)

func TestAuditLogEntryRoundTripAndValidation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)

	tests := []struct {
		name          string
		input         contracts.AuditLogEntry
		expectedValid bool
	}{
		{
			name: "Valid AuditLogEntry (agent actor)",
			input: contracts.AuditLogEntry{
				LogID:     "log_001",
				EventType: contracts.AuditEventActionProposed,
				Timestamp: now,
				Actor: contracts.ActorRef{
					Type:         contracts.ActorTypeAgent,
					SkillName:    ptrString("action-drafting"),
					SkillVersion: ptrString("0.1.0"),
				},
				RelatedActionID: ptrString("action_777"),
				Detail:          ptrString("Proposed buy order of 15 AAPL"),
			},
			expectedValid: true,
		},
		{
			name: "Valid AuditLogEntry (human actor)",
			input: contracts.AuditLogEntry{
				LogID:     "log_002",
				EventType: contracts.AuditEventApprovalGranted,
				Timestamp: now,
				Actor: contracts.ActorRef{
					Type:   contracts.ActorTypeHuman,
					UserID: ptrString("user_123"),
				},
				RelatedActionID: ptrString("action_777"),
				Detail:          ptrString("User approved proposed action_777"),
			},
			expectedValid: true,
		},
		{
			name: "Missing log ID (invalid)",
			input: contracts.AuditLogEntry{
				LogID:     "",
				EventType: contracts.AuditEventActionProposed,
				Timestamp: now,
				Actor: contracts.ActorRef{
					Type: contracts.ActorTypeAgent,
				},
			},
			expectedValid: false,
		},
		{
			name: "Invalid event type enum (invalid)",
			input: contracts.AuditLogEntry{
				LogID:     "log_001",
				EventType: contracts.AuditEventType("unknown_event"),
				Timestamp: now,
				Actor: contracts.ActorRef{
					Type: contracts.ActorTypeAgent,
				},
			},
			expectedValid: false,
		},
		{
			name: "Missing/invalid actor type (invalid)",
			input: contracts.AuditLogEntry{
				LogID:     "log_001",
				EventType: contracts.AuditEventActionProposed,
				Timestamp: now,
				Actor: contracts.ActorRef{
					Type: contracts.ActorType("system"),
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

				var actual contracts.AuditLogEntry
				if err := json.Unmarshal(data, &actual); err != nil {
					t.Fatalf("failed to unmarshal: %v", err)
				}

				actual.Timestamp = actual.Timestamp.UTC()

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
