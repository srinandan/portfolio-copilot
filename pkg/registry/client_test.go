package registry

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

// createZip creates an in-memory zip archive containing the specified files.
func createZip(files map[string][]byte) []byte {
	buf := new(bytes.Buffer)
	zw := zip.NewWriter(buf)
	for name, content := range files {
		w, err := zw.Create(name)
		if err != nil {
			panic(err)
		}
		if _, err := w.Write(content); err != nil {
			panic(err)
		}
	}
	if err := zw.Close(); err != nil {
		panic(err)
	}
	return buf.Bytes()
}

func TestListAuthorizedSkills_SinglePage(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/projects/test-project/locations/test-location/skills" {
			t.Errorf("unexpected path: %s", r.URL.Path)
			http.NotFound(w, r)
			return
		}
		resp := listSkillsResponse{
			Skills: []Skill{
				{
					Name:            "projects/test-project/locations/test-location/skills/private-a",
					TargetState:     "TARGET_STATE_ACTIVE",
					DefaultRevision: "rev1",
				},
				{
					Name:            "projects/test-project/locations/test-location/skills/private-b",
					TargetState:     "TARGET_STATE_DISABLED",
					DefaultRevision: "rev2",
				},
				{
					Name:            "projects/test-project/locations/test-location/skills/private-c",
					TargetState:     "TARGET_STATE_DRAFT",
					DefaultRevision: "rev3",
				},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	skills, err := client.ListAuthorizedSkills(context.Background())
	if err != nil {
		t.Fatalf("ListAuthorizedSkills failed: %v", err)
	}

	if len(skills) != 2 {
		t.Fatalf("expected 2 skills, got %d", len(skills))
	}
	if skills[0].Name != "projects/test-project/locations/test-location/skills/private-a" || skills[0].TargetState != "TARGET_STATE_ACTIVE" {
		t.Errorf("unexpected skill 0: %+v", skills[0])
	}
	if skills[1].Name != "projects/test-project/locations/test-location/skills/private-c" || skills[1].TargetState != "TARGET_STATE_DRAFT" {
		t.Errorf("unexpected skill 1: %+v", skills[1])
	}
}

func TestListAuthorizedSkills_MultiplePages(t *testing.T) {
	var reqCount int32

	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&reqCount, 1)
		w.Header().Set("Content-Type", "application/json")

		if r.URL.Query().Get("pageToken") == "page2" {
			resp := listSkillsResponse{
				Skills: []Skill{
					{
						Name:            "skills/private-b",
						TargetState:     "TARGET_STATE_ACTIVE",
						DefaultRevision: "rev2",
					},
				},
			}
			_ = json.NewEncoder(w).Encode(resp)
			return
		}

		resp := listSkillsResponse{
			Skills: []Skill{
				{
					Name:            "skills/private-a",
					TargetState:     "TARGET_STATE_ACTIVE",
					DefaultRevision: "rev1",
				},
			},
			NextPageToken: "page2",
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	skills, err := client.ListAuthorizedSkills(context.Background())
	if err != nil {
		t.Fatalf("ListAuthorizedSkills failed: %v", err)
	}

	if atomic.LoadInt32(&reqCount) != 2 {
		t.Errorf("expected 2 requests, got %d", reqCount)
	}
	if len(skills) != 2 {
		t.Fatalf("expected 2 skills, got %d", len(skills))
	}
	if skills[0].Name != "skills/private-a" || skills[1].Name != "skills/private-b" {
		t.Errorf("unexpected skills result: %+v", skills)
	}
}

func TestListAuthorizedSkills_APIError(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	_, err = client.ListAuthorizedSkills(context.Background())
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "API returned status 500") {
		t.Errorf("expected status 500 error, got %v", err)
	}
}

func TestListAuthorizedSkills_RevocationScenario(t *testing.T) {
	var isRevoked int32

	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		state := "TARGET_STATE_ACTIVE"
		if atomic.LoadInt32(&isRevoked) == 1 {
			state = "TARGET_STATE_DISABLED"
		}
		resp := listSkillsResponse{
			Skills: []Skill{
				{
					Name:            "skills/private-revokable",
					TargetState:     state,
					DefaultRevision: "rev1",
				},
			},
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	// Call 1: Active
	skills, err := client.ListAuthorizedSkills(context.Background())
	if err != nil {
		t.Fatalf("ListAuthorizedSkills failed: %v", err)
	}
	if len(skills) != 1 || skills[0].Name != "skills/private-revokable" {
		t.Fatalf("expected 1 active skill, got %+v", skills)
	}

	// Simulate revocation
	atomic.StoreInt32(&isRevoked, 1)

	// Call 2: Disabled -> filtered out
	skills, err = client.ListAuthorizedSkills(context.Background())
	if err != nil {
		t.Fatalf("ListAuthorizedSkills failed: %v", err)
	}
	if len(skills) != 0 {
		t.Fatalf("expected 0 skills after revocation, got %d", len(skills))
	}
}

func TestGetSkillContent_Success(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("alt") == "media" {
			if r.URL.Path != "/v1/projects/p/locations/l/skills/private-my-skill/revisions/rev1" {
				t.Errorf("unexpected revision path: %s", r.URL.Path)
			}
			zipBytes := createZip(map[string][]byte{"SKILL.md": []byte("# My Skill Doc")})
			w.Header().Set("Content-Type", "application/zip")
			_, _ = w.Write(zipBytes)
			return
		}

		if r.URL.Path != "/v1/projects/test-project/locations/test-location/skills/private-my-skill" {
			t.Errorf("unexpected skill path: %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(Skill{
			Name:            "projects/test-project/locations/test-location/skills/private-my-skill",
			DefaultRevision: "projects/p/locations/l/skills/private-my-skill/revisions/rev1",
		})
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	content, err := client.GetSkillContent(context.Background(), "my-skill")
	if err != nil {
		t.Fatalf("GetSkillContent failed: %v", err)
	}
	if content != "# My Skill Doc" {
		t.Errorf("expected '# My Skill Doc', got %q", content)
	}
}

func TestGetSkillContent_SubdirSKILLmd(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("alt") == "media" {
			zipBytes := createZip(map[string][]byte{
				"some-dir/SKILL.md": []byte("# Subdir Skill Doc"),
				"README.md":         []byte("# Readme"),
			})
			w.Header().Set("Content-Type", "application/zip")
			_, _ = w.Write(zipBytes)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(Skill{
			Name:            "projects/test-project/locations/test-location/skills/private-my-skill",
			DefaultRevision: "rev1",
		})
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	content, err := client.GetSkillContent(context.Background(), "my-skill")
	if err != nil {
		t.Fatalf("GetSkillContent failed: %v", err)
	}
	if content != "# Subdir Skill Doc" {
		t.Errorf("expected '# Subdir Skill Doc', got %q", content)
	}
}

func TestGetSkillContent_SkillAPIError(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "Skill not found", http.StatusNotFound)
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	_, err = client.GetSkillContent(context.Background(), "nonexistent")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "API returned status 404") {
		t.Errorf("expected status 404 error, got %v", err)
	}
}

func TestGetSkillContent_MissingDefaultRevision(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(Skill{
			Name:            "projects/test-project/locations/test-location/skills/private-my-skill",
			DefaultRevision: "",
		})
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	_, err = client.GetSkillContent(context.Background(), "my-skill")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "has no default revision") {
		t.Errorf("expected 'has no default revision' error, got %v", err)
	}
}

func TestGetSkillContent_RevisionAPIError(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("alt") == "media" {
			http.Error(w, "Failed to download zip", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(Skill{
			Name:            "skills/private-my-skill",
			DefaultRevision: "rev1",
		})
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	_, err = client.GetSkillContent(context.Background(), "my-skill")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "API returned status 500 fetching revision") {
		t.Errorf("expected status 500 error, got %v", err)
	}
}

func TestGetSkillContent_MissingSKILLmd(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("alt") == "media" {
			zipBytes := createZip(map[string][]byte{"other_file.txt": []byte("some content")})
			w.Header().Set("Content-Type", "application/zip")
			_, _ = w.Write(zipBytes)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(Skill{
			Name:            "skills/private-my-skill",
			DefaultRevision: "rev1",
		})
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	_, err = client.GetSkillContent(context.Background(), "my-skill")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "SKILL.md not found in revision zip") {
		t.Errorf("expected 'SKILL.md not found in revision zip' error, got %v", err)
	}
}

func TestGetSkillContent_InvalidZip(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("alt") == "media" {
			w.Header().Set("Content-Type", "application/zip")
			_, _ = w.Write([]byte("invalid non-zip data"))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(Skill{
			Name:            "skills/private-my-skill",
			DefaultRevision: "rev1",
		})
	}))
	defer ts.Close()

	client, err := NewClient(
		context.Background(),
		"test-project",
		"test-location",
		WithBaseURL(ts.URL+"/v1"),
		WithHTTPClient(ts.Client()),
	)
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	_, err = client.GetSkillContent(context.Background(), "my-skill")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "failed to read zip archive") {
		t.Errorf("expected 'failed to read zip archive' error, got %v", err)
	}
}
