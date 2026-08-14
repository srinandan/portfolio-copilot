package bigquery

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
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

// TransactionRecord represents a single row in a transactions table (e.g. checking_transactions).
type TransactionRecord struct {
	UserID             string  `bigquery:"user_id" json:"user_id"`
	TransactionDate    string  `bigquery:"transaction_date" json:"transaction_date"` // YYYY-MM-DD
	Amount             float64 `bigquery:"amount" json:"amount"`
	Description        string  `bigquery:"description" json:"description"`
	RawCategory        string  `bigquery:"raw_category" json:"raw_category"`
	NormalizedCategory string  `bigquery:"normalized_category" json:"normalized_category"`
}

// Loader is an interface for writing transactions to BigQuery.
type Loader interface {
	InsertTransactions(ctx context.Context, datasetName, tableName string, rows []TransactionRecord) error
}

// Runner is an interface for BigQuery execution and loading.
type Runner interface {
	RunSecureQuery(ctx context.Context, generatedSQL, userID string) ([]map[string]bigquery.Value, error)
	InsertTransactions(ctx context.Context, datasetName, tableName string, rows []TransactionRecord) error
}

// BigQueryRunner handles running generated SQL safely and inserting rows.
type BigQueryRunner struct {
	client *bigquery.Client
}

// NewBigQueryRunner creates a new BigQueryRunner
func NewBigQueryRunner(client *bigquery.Client) *BigQueryRunner {
	return &BigQueryRunner{client: client}
}

// InsertTransactions streams rows into a BigQuery dataset table using deterministic insertIDs for deduplication.
func (r *BigQueryRunner) InsertTransactions(ctx context.Context, datasetName, tableName string, rows []TransactionRecord) error {
	ctx, span := tracer.Start(ctx, "bigquery.InsertTransactions", trace.WithAttributes(
		attribute.String("dataset", datasetName),
		attribute.String("table", tableName),
		attribute.Int("rows_count", len(rows)),
	))
	defer span.End()

	if len(rows) == 0 {
		return nil
	}

	savers := make([]*bigquery.StructSaver, len(rows))
	for i, row := range rows {
		// Deterministic insertID based on row content hash provides BigQuery streaming deduplication
		hash := sha256.Sum256([]byte(fmt.Sprintf("%s:%s:%.4f:%s:%s:%s", row.UserID, row.TransactionDate, row.Amount, row.Description, row.RawCategory, row.NormalizedCategory)))
		savers[i] = &bigquery.StructSaver{
			Struct:   row,
			InsertID: hex.EncodeToString(hash[:16]),
		}
	}

	inserter := r.client.Dataset(datasetName).Table(tableName).Inserter()
	if err := inserter.Put(ctx, savers); err != nil {
		span.RecordError(err)
		return fmt.Errorf("failed to insert transactions into BigQuery table %s.%s: %w", datasetName, tableName, err)
	}
	return nil
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
