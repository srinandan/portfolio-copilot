package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestSPARoutes_ServesIndexForRoot(t *testing.T) {
	gin.SetMode(gin.TestMode)
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "index.html"), []byte("<html>root-index</html>"), 0o644); err != nil {
		t.Fatalf("write index: %v", err)
	}

	r := gin.New()
	setupSPARoutes(r, dir)

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", w.Code)
	}
	if !strings.Contains(w.Body.String(), "root-index") {
		t.Errorf("body = %q, want index.html contents", w.Body.String())
	}
}

func TestSPARoutes_ServesStaticAsset(t *testing.T) {
	gin.SetMode(gin.TestMode)
	dir := t.TempDir()
	assetsDir := filepath.Join(dir, "assets")
	if err := os.MkdirAll(assetsDir, 0o755); err != nil {
		t.Fatalf("mkdir assets: %v", err)
	}
	if err := os.WriteFile(filepath.Join(assetsDir, "app.js"), []byte("console.log('app');"), 0o644); err != nil {
		t.Fatalf("write app.js: %v", err)
	}

	r := gin.New()
	setupSPARoutes(r, dir)

	req := httptest.NewRequest(http.MethodGet, "/assets/app.js", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", w.Code)
	}
	if !strings.Contains(w.Body.String(), "console.log('app');") {
		t.Errorf("body = %q, want app.js contents", w.Body.String())
	}
}

func TestSPARoutes_ClientRouteFallbackToIndex(t *testing.T) {
	gin.SetMode(gin.TestMode)
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "index.html"), []byte("<html>spa-app</html>"), 0o644); err != nil {
		t.Fatalf("write index: %v", err)
	}

	r := gin.New()
	setupSPARoutes(r, dir)

	req := httptest.NewRequest(http.MethodGet, "/portfolio/drift", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", w.Code)
	}
	if !strings.Contains(w.Body.String(), "spa-app") {
		t.Errorf("body = %q, want index.html contents", w.Body.String())
	}
}

func TestSPARoutes_MissingAssetWithExtensionReturns404(t *testing.T) {
	gin.SetMode(gin.TestMode)
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "index.html"), []byte("<html>spa-app</html>"), 0o644); err != nil {
		t.Fatalf("write index: %v", err)
	}

	r := gin.New()
	setupSPARoutes(r, dir)

	req := httptest.NewRequest(http.MethodGet, "/assets/missing.js", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("status = %d, want 404 for missing static asset with extension", w.Code)
	}
}

func TestSPARoutes_APIRouteNotFoundReturns404JSON(t *testing.T) {
	gin.SetMode(gin.TestMode)
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "index.html"), []byte("<html>spa-app</html>"), 0o644); err != nil {
		t.Fatalf("write index: %v", err)
	}

	r := gin.New()
	setupSPARoutes(r, dir)

	req := httptest.NewRequest(http.MethodGet, "/api/nonexistent", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("status = %d, want 404 for missing API endpoint", w.Code)
	}
	if !strings.Contains(w.Body.String(), "not found") {
		t.Errorf("body = %q, want json not found error", w.Body.String())
	}
}
