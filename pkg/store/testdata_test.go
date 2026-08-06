package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"portfolio-copilot/pkg/contracts"
)

func TestCanonicalFixturesValidate(t *testing.T) {
	c := getTestClient(t)

	// 1. Validate Holdings fixture
	holdingsPath := filepath.Join("..", "..", "testdata", "holdings.json")
	holdingsBytes, err := os.ReadFile(holdingsPath)
	if err != nil {
		t.Fatalf("failed to read %s: %v", holdingsPath, err)
	}

	var holdings contracts.HoldingsSnapshot
	if err := json.Unmarshal(holdingsBytes, &holdings); err != nil {
		t.Fatalf("failed to unmarshal holdings JSON: %v", err)
	}

	if err := validate(c.holdingsSchema, &holdings); err != nil {
		t.Errorf("testdata/holdings.json failed schema validation: %v", err)
	}

	// 2. Validate Liabilities fixture
	liabilitiesPath := filepath.Join("..", "..", "testdata", "liabilities.json")
	liabilitiesBytes, err := os.ReadFile(liabilitiesPath)
	if err != nil {
		t.Fatalf("failed to read %s: %v", liabilitiesPath, err)
	}

	var liabilities contracts.LiabilitiesSnapshot
	if err := json.Unmarshal(liabilitiesBytes, &liabilities); err != nil {
		t.Fatalf("failed to unmarshal liabilities JSON: %v", err)
	}

	if err := validate(c.liabilitiesSchema, &liabilities); err != nil {
		t.Errorf("testdata/liabilities.json failed schema validation: %v", err)
	}

	// 3. Validate IPS fixture
	ipsPath := filepath.Join("..", "..", "testdata", "ips.json")
	ipsBytes, err := os.ReadFile(ipsPath)
	if err != nil {
		t.Fatalf("failed to read %s: %v", ipsPath, err)
	}

	var ips contracts.InvestmentPolicyStatement
	if err := json.Unmarshal(ipsBytes, &ips); err != nil {
		t.Fatalf("failed to unmarshal ips JSON: %v", err)
	}

	if err := validate(c.ipsSchema, &ips); err != nil {
		t.Errorf("testdata/ips.json failed schema validation: %v", err)
	}
}
