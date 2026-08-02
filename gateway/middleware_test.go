package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
)

func TestStructuredLogMiddleware_ExtractsTraceID(t *testing.T) {
	gin.SetMode(gin.TestMode)

	InitLogger()

	r := gin.New()
	r.Use(StructuredLogMiddleware())

	var extractedTraceID string

	r.GET("/test", func(c *gin.Context) {
		extractedTraceID = GetTraceID(c.Request.Context())
		c.String(http.StatusOK, "ok")
	})

	req, _ := http.NewRequest("GET", "/test", nil)
	req.Header.Set("X-Cloud-Trace-Context", "test-trace-id-123")

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "test-trace-id-123", extractedTraceID)
}

func TestGetTraceID_Empty(t *testing.T) {
	ctx := context.Background()
	assert.Equal(t, "", GetTraceID(ctx))
}
