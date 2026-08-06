package main

import (
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/gin-gonic/gin"
)

// setupSPARoutes mounts SPA static file serving with client-side history mode fallback.
// When staticDir is empty, it checks os.Getenv("STATIC_DIR") and common paths (/app/dist, ./frontend/dist, ./dist).
func setupSPARoutes(r *gin.Engine, staticDir string) {
	if staticDir == "" {
		staticDir = os.Getenv("STATIC_DIR")
	}
	if staticDir == "" {
		for _, candidate := range []string{"/app/dist", "./frontend/dist", "./dist"} {
			if info, err := os.Stat(candidate); err == nil && info.IsDir() {
				staticDir = candidate
				break
			}
		}
	}
	if staticDir == "" {
		slog.Info("no static directory found, SPA serving disabled")
		return
	}
	slog.Info("serving SPA static files", "dir", staticDir)

	r.NoRoute(func(c *gin.Context) {
		reqPath := c.Request.URL.Path

		// Never handle /api/* or /health with the SPA fallback
		if strings.HasPrefix(reqPath, "/api/") || reqPath == "/health" {
			c.JSON(http.StatusNotFound, gin.H{"error": "not found"})
			return
		}

		cleanPath := filepath.Join(staticDir, filepath.Clean(reqPath))
		if info, err := os.Stat(cleanPath); err == nil && !info.IsDir() {
			c.File(cleanPath)
			return
		}

		// If the requested path has a file extension (e.g. .js, .css, .png) and doesn't exist,
		// return 404 rather than index.html so browsers don't try to parse HTML as scripts.
		if strings.Contains(filepath.Base(reqPath), ".") {
			c.Status(http.StatusNotFound)
			return
		}

		// Client-side routing fallback: serve index.html
		indexPath := filepath.Join(staticDir, "index.html")
		if _, err := os.Stat(indexPath); err == nil {
			c.File(indexPath)
			return
		}

		c.JSON(http.StatusNotFound, gin.H{"error": "index.html not found"})
	})
}
