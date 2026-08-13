package store

import (
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"os"

	"cloud.google.com/go/firestore"
	"github.com/xeipuuv/gojsonschema"
	"go.opentelemetry.io/otel"
	"portfolio-copilot/pkg/contracts"
)

//go:embed schemas/*.schema.json
var schemaFS embed.FS

// tracer emits child spans for Firestore reads/writes so they nest under the
// incoming request's server span in Cloud Trace.
var tracer = otel.Tracer("portfolio-copilot/pkg/store")

// Store is an interface for the Firestore client wrappers to allow for easier testing.
type Store interface {
	SetHoldings(ctx context.Context, userID string, snapshot *contracts.HoldingsSnapshot) error
	SetLiabilities(ctx context.Context, userID string, snapshot *contracts.LiabilitiesSnapshot) error
	AppendAuditLog(ctx context.Context, entry *contracts.AuditLogEntry) error
	UpdateIPS(ctx context.Context, ips *contracts.InvestmentPolicyStatement) error
	SetUserProfile(ctx context.Context, userID string, profile *contracts.UserProfile) error
	GetUserProfile(ctx context.Context, userID string) (*contracts.UserProfile, error)
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
