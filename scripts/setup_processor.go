package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"strings"

	documentai "cloud.google.com/go/documentai/apiv1"
	"cloud.google.com/go/documentai/apiv1/documentaipb"
	"google.golang.org/api/iterator"
	"google.golang.org/api/option"
)

func main() {
	projectID := flag.String("project", "", "GCP Project ID")
	location := flag.String("location", "us", "Document AI location (us or eu)")
	displayName := flag.String("display-name", "portfolio-copilot-w2-processor", "Processor display name")
	processorType := flag.String("type", "FORM_W2_PROCESSOR", "Processor type (e.g. FORM_W2_PROCESSOR or FORM_PARSER_PROCESSOR)")
	flag.Parse()

	if *projectID == "" {
		*projectID = os.Getenv("GOOGLE_CLOUD_PROJECT")
		if *projectID == "" {
			*projectID = os.Getenv("PROJECT_ID")
		}
	}
	if *projectID == "" {
		fmt.Fprintf(os.Stderr, "Error: project ID is required\n")
		os.Exit(1)
	}

	ctx := context.Background()
	endpoint := fmt.Sprintf("%s-documentai.googleapis.com:443", *location)
	client, err := documentai.NewDocumentProcessorClient(ctx, option.WithEndpoint(endpoint))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create Document AI client: %v\n", err)
		os.Exit(1)
	}
	defer client.Close()

	parent := fmt.Sprintf("projects/%s/locations/%s", *projectID, *location)

	// 1. List existing processors to check if one already exists
	req := &documentaipb.ListProcessorsRequest{
		Parent: parent,
	}
	it := client.ListProcessors(ctx, req)
	for {
		proc, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to list processors: %v\n", err)
			break
		}
		if proc.DisplayName == *displayName || proc.Type == *processorType {
			parts := strings.Split(proc.Name, "/")
			procID := parts[len(parts)-1]
			fmt.Fprintf(os.Stderr, "Found existing Document AI processor: %s (ID: %s, State: %s)\n", proc.Name, procID, proc.State)
			fmt.Println(procID)
			return
		}
	}

	// 2. Create processor if not found
	fmt.Fprintf(os.Stderr, "Creating Document AI processor %q (type: %s) in %s...\n", *displayName, *processorType, parent)
	createReq := &documentaipb.CreateProcessorRequest{
		Parent: parent,
		Processor: &documentaipb.Processor{
			DisplayName: *displayName,
			Type:        *processorType,
		},
	}

	created, err := client.CreateProcessor(ctx, createReq)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create processor: %v\n", err)
		os.Exit(1)
	}

	parts := strings.Split(created.Name, "/")
	procID := parts[len(parts)-1]
	fmt.Fprintf(os.Stderr, "Successfully created Document AI processor: %s (ID: %s)\n", created.Name, procID)
	fmt.Println(procID)
}
