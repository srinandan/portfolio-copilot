package main

import "testing"

func TestMain(t *testing.T) {
	// A dummy test file to prevent `go: no such tool "covdata"` in Go 1.25
	// when running go test ./... -coverprofile=coverage.out on packages without test files.
}
