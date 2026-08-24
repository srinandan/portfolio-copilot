package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// traceContextKey is used to store the trace ID in the request context
type traceContextKey struct{}

// InitLogger initializes the global slog logger based on the LOG_LEVEL env var.
func InitLogger() {
	logLevelStr := strings.ToUpper(os.Getenv("LOG_LEVEL"))
	var level slog.Level

	switch logLevelStr {
	case "DEBUG":
		level = slog.LevelDebug
	case "WARN", "WARNING":
		level = slog.LevelWarn
	case "ERROR":
		level = slog.LevelError
	case "INFO":
		fallthrough
	default:
		// Default to INFO in production, or if not specified.
		level = slog.LevelInfo
	}

	opts := &slog.HandlerOptions{
		Level: level,
		// Map standard keys to GCP Cloud Logging keys if needed,
		// but GCP usually parses standard JSON logs fine.
		// We can add GCP specific keys like "severity" via ReplaceAttr if needed.
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			if a.Key == slog.LevelKey {
				// GCP expects "severity" instead of "level"
				a.Key = "severity"
			} else if a.Key == slog.MessageKey {
				// GCP expects "message" which slog uses by default.
			}
			return a
		},
	}

	handler := slog.NewJSONHandler(os.Stdout, opts)
	logger := slog.New(handler)
	slog.SetDefault(logger)
}

// StructuredLogMiddleware is a Gin middleware that handles structured logging
// and trace propagation.
func StructuredLogMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()

		// Extract trace IDs
		traceID := c.GetHeader("X-Cloud-Trace-Context")
		if traceID == "" {
			traceID = c.GetHeader("traceparent")
		}
		if traceID == "" {
			traceID = c.GetHeader("X-Request-ID")
		}

		// Inject traceID into Go context if present
		if traceID != "" {
			ctx := context.WithValue(c.Request.Context(), traceContextKey{}, traceID)
			c.Request = c.Request.WithContext(ctx)
		}

		path := c.Request.URL.Path
		raw := c.Request.URL.RawQuery
		if raw != "" {
			path = path + "?" + raw
		}

		// Process request
		c.Next()

		// Log request details
		duration := time.Since(start)
		status := c.Writer.Status()

		logger := slog.Default()
		if traceID != "" {
			logger = logger.With("logging.googleapis.com/trace", traceID)
		}

		logger.InfoContext(c.Request.Context(), "HTTP Request",
			slog.String("method", c.Request.Method),
			slog.String("path", path),
			slog.Int("status", status),
			slog.Duration("duration", duration),
			slog.String("client_ip", c.ClientIP()),
			slog.String("error", c.Errors.ByType(gin.ErrorTypePrivate).String()),
		)
	}
}

// GetTraceID extracts the trace ID from the context, if any.
func GetTraceID(ctx context.Context) string {
	if val, ok := ctx.Value(traceContextKey{}).(string); ok {
		return val
	}
	return ""
}

// SecurityHeadersMiddleware attaches standard defensive HTTP headers to all responses.
func SecurityHeadersMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Header("X-Content-Type-Options", "nosniff")
		c.Header("X-Frame-Options", "DENY")
		c.Header("X-XSS-Protection", "1; mode=block")
		c.Header("Referrer-Policy", "strict-origin-when-cross-origin")
		c.Header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self' https:;")

		if c.Request.TLS != nil || c.GetHeader("X-Forwarded-Proto") == "https" {
			c.Header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
		}

		c.Next()
	}
}

// MaxBodySizeMiddleware limits the maximum readable size of the request body to prevent memory/disk exhaustion.
func MaxBodySizeMiddleware(maxBytes int64) gin.HandlerFunc {
	return func(c *gin.Context) {
		if c.Request.Body != nil {
			c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, maxBytes)
		}
		c.Next()
	}
}

