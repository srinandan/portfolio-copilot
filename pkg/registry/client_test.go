package registry

import (
	"archive/zip"
	"bytes"
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestClient_ListAuthorizedSkills(t *testing.T) {
	tests := []struct {
		name       string
		responses  []string
		status     int
		wantSkills []Skill
		wantErr    bool
	}{
		{
			name: "single page, filters out disabled",
			responses: []string{
				`{
					"skills": [
						{"name": "skills/private-a", "targetState": "TARGET_STATE_ACTIVE", "defaultRevision": "rev1"},
						{"name": "skills/private-b", "targetState": "TARGET_STATE_DISABLED", "defaultRevision": "rev2"},
						{"name": "skills/private-c", "targetState": "TARGET_STATE_DRAFT", "defaultRevision": "rev3"}
					]
				}`,
			},
			status: http.StatusOK,
			wantSkills: []Skill{
				{Name: "skills/private-a", TargetState: "TARGET_STATE_ACTIVE", DefaultRevision: "rev1"},
				{Name: "skills/private-c", TargetState: "TARGET_STATE_DRAFT", DefaultRevision: "rev3"},
			},
		},
		{
			name: "multiple pages",
			responses: []string{
				`{
					"skills": [
						{"name": "skills/private-a", "targetState": "TARGET_STATE_ACTIVE", "defaultRevision": "rev1"}
					],
					"nextPageToken": "page2"
				}`,
				`{
					"skills": [
						{"name": "skills/private-b", "targetState": "TARGET_STATE_ACTIVE", "defaultRevision": "rev2"}
					]
				}`,
			},
			status: http.StatusOK,
			wantSkills: []Skill{
				{Name: "skills/private-a", TargetState: "TARGET_STATE_ACTIVE", DefaultRevision: "rev1"},
				{Name: "skills/private-b", TargetState: "TARGET_STATE_ACTIVE", DefaultRevision: "rev2"},
			},
		},
		{
			name: "api error",
			responses: []string{
				`{"error": "something went wrong"}`,
			},
			status:  http.StatusInternalServerError,
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			reqCount := 0
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				assert.True(t, strings.HasPrefix(r.URL.Path, "/v1/projects/test-project/locations/test-location/skills"))
				if tt.status != http.StatusOK {
					w.WriteHeader(tt.status)
				}
				fmt.Fprint(w, tt.responses[reqCount])
				reqCount++
			}))
			defer srv.Close()

			c, err := NewClient(context.Background(), "test-project", "test-location", WithBaseURL(srv.URL+"/v1"), WithHTTPClient(srv.Client()))
			require.NoError(t, err)

			got, err := c.ListAuthorizedSkills(context.Background())
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
				assert.Equal(t, tt.wantSkills, got)
				assert.Equal(t, len(tt.responses), reqCount)
			}
		})
	}
}

func TestClient_RevocationScenario(t *testing.T) {
	// Simulate the revocation scenario explicitly: skill authorized -> set to DISABLED -> next query excludes it
	isRevoked := false

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !isRevoked {
			fmt.Fprint(w, `{
				"skills": [
					{"name": "skills/private-revokable", "targetState": "TARGET_STATE_ACTIVE", "defaultRevision": "rev1"}
				]
			}`)
		} else {
			fmt.Fprint(w, `{
				"skills": [
					{"name": "skills/private-revokable", "targetState": "TARGET_STATE_DISABLED", "defaultRevision": "rev1"}
				]
			}`)
		}
	}))
	defer srv.Close()

	c, err := NewClient(context.Background(), "test-project", "test-location", WithBaseURL(srv.URL+"/v1"), WithHTTPClient(srv.Client()))
	require.NoError(t, err)

	// Call 1: Skill is active
	skills, err := c.ListAuthorizedSkills(context.Background())
	require.NoError(t, err)
	assert.Len(t, skills, 1)
	assert.Equal(t, "skills/private-revokable", skills[0].Name)

	// Simulate revocation (e.g. some other process PATCHed it)
	isRevoked = true

	// Call 2: Skill is disabled and should be excluded
	skills, err = c.ListAuthorizedSkills(context.Background())
	require.NoError(t, err)
	assert.Len(t, skills, 0)
}

func TestClient_GetSkillContent(t *testing.T) {
	// Helper to create a valid zip archive containing SKILL.md
	createZip := func(content string, filename string) []byte {
		buf := new(bytes.Buffer)
		w := zip.NewWriter(buf)
		f, err := w.Create(filename)
		require.NoError(t, err)
		_, err = f.Write([]byte(content))
		require.NoError(t, err)
		require.NoError(t, w.Close())
		return buf.Bytes()
	}

	tests := []struct {
		name        string
		skillID     string
		skillResp   string
		skillStatus int
		revResp     []byte
		revStatus   int
		wantContent string
		wantErr     bool
	}{
		{
			name:        "success",
			skillID:     "my-skill",
			skillResp:   `{"name": "skills/private-my-skill", "defaultRevision": "projects/p/locations/l/skills/private-my-skill/revisions/rev1"}`,
			skillStatus: http.StatusOK,
			revResp:     createZip("# My Skill", "SKILL.md"),
			revStatus:   http.StatusOK,
			wantContent: "# My Skill",
		},
		{
			name:        "success in subfolder",
			skillID:     "my-skill",
			skillResp:   `{"name": "skills/private-my-skill", "defaultRevision": "projects/p/locations/l/skills/private-my-skill/revisions/rev1"}`,
			skillStatus: http.StatusOK,
			revResp:     createZip("# My Skill in Subdir", "some-dir/SKILL.md"),
			revStatus:   http.StatusOK,
			wantContent: "# My Skill in Subdir",
		},
		{
			name:        "skill API error",
			skillID:     "my-skill",
			skillStatus: http.StatusNotFound,
			wantErr:     true,
		},
		{
			name:        "revision API error",
			skillID:     "my-skill",
			skillResp:   `{"name": "skills/private-my-skill", "defaultRevision": "rev1"}`,
			skillStatus: http.StatusOK,
			revStatus:   http.StatusNotFound,
			wantErr:     true,
		},
		{
			name:        "missing SKILL.md",
			skillID:     "my-skill",
			skillResp:   `{"name": "skills/private-my-skill", "defaultRevision": "rev1"}`,
			skillStatus: http.StatusOK,
			revResp:     createZip("some other text", "other.txt"),
			revStatus:   http.StatusOK,
			wantErr:     true,
		},
		{
			name:        "invalid zip",
			skillID:     "my-skill",
			skillResp:   `{"name": "skills/private-my-skill", "defaultRevision": "rev1"}`,
			skillStatus: http.StatusOK,
			revResp:     []byte("not a zip file"),
			revStatus:   http.StatusOK,
			wantErr:     true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if strings.Contains(r.URL.Path, "rev1") {
					assert.Equal(t, "media", r.URL.Query().Get("alt"))
					if tt.revStatus != http.StatusOK {
						w.WriteHeader(tt.revStatus)
					}
					w.Write(tt.revResp)
					return
				}

				// Skill fetch
				expectedPath := fmt.Sprintf("/v1/projects/test-project/locations/test-location/skills/private-%s", tt.skillID)
				assert.Equal(t, expectedPath, r.URL.Path)

				if tt.skillStatus != http.StatusOK {
					w.WriteHeader(tt.skillStatus)
				}
				fmt.Fprint(w, tt.skillResp)
			}))
			defer srv.Close()

			c, err := NewClient(context.Background(), "test-project", "test-location", WithBaseURL(srv.URL+"/v1"), WithHTTPClient(srv.Client()))
			require.NoError(t, err)

			got, err := c.GetSkillContent(context.Background(), tt.skillID)
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
				assert.Equal(t, tt.wantContent, got)
			}
		})
	}
}
