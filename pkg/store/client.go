package store

import (
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"strings"

	"cloud.google.com/go/firestore"
	"github.com/xeipuuv/gojsonschema"
	"go.opentelemetry.io/otel"
	"portfolio-copilot/pkg/contracts"
)

//go:embed schemas/*.schema.json
var schemaFS embed.FS

var validUserIDRegex = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,64}$`)

// ValidateUserID verifies that a user_id conforms to the safe identifier format ^[a-zA-Z0-9_-]{1,64}$.
func ValidateUserID(userID string) error {
	trimmed := strings.TrimSpace(userID)
	if trimmed == "" || !validUserIDRegex.MatchString(trimmed) {
		return fmt.Errorf("invalid user_id format: %q", userID)
	}
	return nil
}

// tracer emits child spans for Firestore reads/writes so they nest under the
// incoming request's server span in Cloud Trace.
var tracer = otel.Tracer("portfolio-copilot/pkg/store")

// Store is an interface for the Firestore client wrappers to allow for easier testing.
type Store interface {
	SetHoldings(ctx context.Context, userID string, snapshot *contracts.HoldingsSnapshot) error
	GetHoldings(ctx context.Context, userID string) (*contracts.HoldingsSnapshot, error)
	SetLiabilities(ctx context.Context, userID string, snapshot *contracts.LiabilitiesSnapshot) error
	GetLiabilities(ctx context.Context, userID string) (*contracts.LiabilitiesSnapshot, error)
	AppendAuditLog(ctx context.Context, entry *contracts.AuditLogEntry) error
	UpdateIPS(ctx context.Context, ips *contracts.InvestmentPolicyStatement) error
	GetActiveIPS(ctx context.Context, userID string) (*contracts.InvestmentPolicyStatement, error)
	SetUserProfile(ctx context.Context, userID string, profile *contracts.UserProfile) error
	GetUserProfile(ctx context.Context, userID string) (*contracts.UserProfile, error)
	GetSpendingReport(ctx context.Context, userID string) (*contracts.SpendingReport, error)
	GetDriftReport(ctx context.Context, userID string) (*contracts.DriftReport, error)
	GetDocuments(ctx context.Context, userID string) ([]contracts.DocumentItem, error)
	SetDocument(ctx context.Context, item *contracts.DocumentItem) error
	SetW2Document(ctx context.Context, doc *contracts.W2Document) error
	GetW2Documents(ctx context.Context, userID string) ([]contracts.W2Document, error)
	GetW2Document(ctx context.Context, userID string, docID string) (*contracts.W2Document, error)
	DeleteW2Document(ctx context.Context, userID string, docID string) error
}

// Client wraps a real Firestore client.
type Client struct {
	fs *firestore.Client

	// preloaded JSON schema loaders
	ipsSchema         *gojsonschema.Schema
	holdingsSchema    *gojsonschema.Schema
	liabilitiesSchema *gojsonschema.Schema
	auditLogSchema    *gojsonschema.Schema
	userProfileSchema *gojsonschema.Schema
	w2Schema          *gojsonschema.Schema
}

// NewClient initializes a new Client using ADC and the PROJECT_ID env var.
func NewClient(ctx context.Context) (*Client, error) {
	projectID := os.Getenv("PROJECT_ID")
	if projectID == "" {
		return nil, fmt.Errorf("PROJECT_ID environment variable is not set")
	}

	fsClient, err := firestore.NewClient(ctx, projectID)
	if err != nil {
		return nil, fmt.Errorf("failed to create firestore client: %w", err)
	}

	c := &Client{
		fs: fsClient,
	}

	if err := c.loadSchemas(); err != nil {
		return nil, err
	}

	return c, nil
}

func (c *Client) loadSchemas() error {
	loaders := map[string]**gojsonschema.Schema{
		"schemas/ips.schema.json":             &c.ipsSchema,
		"schemas/holdings.schema.json":        &c.holdingsSchema,
		"schemas/liabilities.schema.json":     &c.liabilitiesSchema,
		"schemas/audit-log-entry.schema.json": &c.auditLogSchema,
		"schemas/user-profile.schema.json":    &c.userProfileSchema,
		"schemas/w2-document.schema.json":     &c.w2Schema,
	}

	for path, schemaPtr := range loaders {
		data, err := schemaFS.ReadFile(path)
		if err != nil {
			return fmt.Errorf("failed to read embedded schema %s: %w", path, err)
		}
		loader := gojsonschema.NewBytesLoader(data)
		schema, err := gojsonschema.NewSchema(loader)
		if err != nil {
			return fmt.Errorf("failed to load schema %s: %w", path, err)
		}
		*schemaPtr = schema
	}

	return nil
}

// Close closes the underlying Firestore client.
func (c *Client) Close() error {
	if c.fs != nil {
		return c.fs.Close()
	}
	return nil
}

// validate checks if the given data struct satisfies the provided schema.
func validate(schema *gojsonschema.Schema, data interface{}) error {
	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal data for validation: %w", err)
	}

	documentLoader := gojsonschema.NewBytesLoader(jsonData)
	result, err := schema.Validate(documentLoader)
	if err != nil {
		return fmt.Errorf("schema validation error: %w", err)
	}

	if !result.Valid() {
		var errs []string
		for _, desc := range result.Errors() {
			errs = append(errs, desc.String())
		}
		return fmt.Errorf("data failed schema validation: %v", errs)
	}

	return nil
}
