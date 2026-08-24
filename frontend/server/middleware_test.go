package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
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

func TestSecurityHeadersMiddleware_DefaultHeaders(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(SecurityHeadersMiddleware())

	r.GET("/ping", func(c *gin.Context) {
		c.String(http.StatusOK, "pong")
	})

	req, _ := http.NewRequest(http.MethodGet, "/ping", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "nosniff", w.Header().Get("X-Content-Type-Options"))
	assert.Equal(t, "DENY", w.Header().Get("X-Frame-Options"))
	assert.Equal(t, "1; mode=block", w.Header().Get("X-XSS-Protection"))
	assert.Equal(t, "strict-origin-when-cross-origin", w.Header().Get("Referrer-Policy"))
	assert.Contains(t, w.Header().Get("Content-Security-Policy"), "default-src 'self'")
	assert.Empty(t, w.Header().Get("Strict-Transport-Security"))
}

func TestSecurityHeadersMiddleware_HSTSOnHTTPS(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(SecurityHeadersMiddleware())

	r.GET("/ping", func(c *gin.Context) {
		c.String(http.StatusOK, "pong")
	})

	req, _ := http.NewRequest(http.MethodGet, "/ping", nil)
	req.Header.Set("X-Forwarded-Proto", "https")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "max-age=31536000; includeSubDomains", w.Header().Get("Strict-Transport-Security"))
}

func TestMaxBodySizeMiddleware_EnforcesLimit(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.POST("/upload", MaxBodySizeMiddleware(10), func(c *gin.Context) {
		buf := make([]byte, 20)
		_, err := c.Request.Body.Read(buf)
		if err != nil && err.Error() == "http: request body too large" {
			c.String(http.StatusRequestEntityTooLarge, "too large")
			return
		}
		c.String(http.StatusOK, "ok")
	})

	// Under limit
	reqSmall, _ := http.NewRequest(http.MethodPost, "/upload", strings.NewReader("12345"))
	wSmall := httptest.NewRecorder()
	r.ServeHTTP(wSmall, reqSmall)
	assert.Equal(t, http.StatusOK, wSmall.Code)

	// Over limit
	reqLarge, _ := http.NewRequest(http.MethodPost, "/upload", strings.NewReader("12345678901234567890"))
	wLarge := httptest.NewRecorder()
	r.ServeHTTP(wLarge, reqLarge)
	assert.Equal(t, http.StatusRequestEntityTooLarge, wLarge.Code)
}

