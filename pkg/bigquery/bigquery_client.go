package bigquery

import (
	"context"
	"fmt"

	"cloud.google.com/go/bigquery"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
	"google.golang.org/api/iterator"
)

// tracer emits a child span for each analytics query so BigQuery reads nest
// under the incoming request's server span in Cloud Trace.
var tracer = otel.Tracer("portfolio-copilot/pkg/bigquery")

// BigQueryRunner handles running generated SQL safely
type BigQueryRunner struct {
	client *bigquery.Client
}

// NewBigQueryRunner creates a new BigQueryRunner
func NewBigQueryRunner(client *bigquery.Client) *BigQueryRunner {
	return &BigQueryRunner{client: client}
}

// RunSecureQuery enforces row-level user_id scoping and byte ceilings, and executes the query
func (r *BigQueryRunner) RunSecureQuery(ctx context.Context, generatedSQL, userID string) ([]map[string]bigquery.Value, error) {
	ctx, span := tracer.Start(ctx, "bigquery.RunSecureQuery", trace.WithAttributes(attribute.String("user_id", userID)))
	defer span.End()

	// Let PrepareSecureSQL handle the constraints and rewriting
	secureSQL, params, err := PrepareSecureSQL(generatedSQL, userID)
	if err != nil {
		span.RecordError(err)
		return nil, fmt.Errorf("invalid query: %w", err)
	}

	q := r.client.Query(secureSQL)

	// Set parameters
	q.Parameters = []bigquery.QueryParameter{
		{
			Name:  "user_id",
			Value: params["user_id"],
		},
	}

	// Set byte-scan ceiling to prevent full-table scans
	q.MaxBytesBilled = MaxBytesBilled

	it, err := q.Read(ctx)
	if err != nil {
		span.RecordError(err)
		return nil, fmt.Errorf("error executing query: %w", err)
	}

	var results []map[string]bigquery.Value
	for {
		var row map[string]bigquery.Value
		err := it.Next(&row)
		if err == iterator.Done {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("error reading row: %w", err)
		}
		results = append(results, row)
	}

	return results, nil
}
