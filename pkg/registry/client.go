package registry

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"

	"golang.org/x/oauth2/google"
)

const defaultBaseURL = "https://agentregistry.googleapis.com/v1"

// Client is a REST client for the Google Cloud Agent Registry API.
type Client struct {
	httpClient *http.Client
	baseURL    string
	projectID  string
	location   string
}

// ClientOption allows customizing the client.
type ClientOption func(*Client)

// WithBaseURL overrides the default base URL for the Agent Registry API.
// Mostly used for testing with a mock server.
func WithBaseURL(baseURL string) ClientOption {
	return func(c *Client) {
		c.baseURL = baseURL
	}
}

// WithHTTPClient overrides the default authenticated HTTP client.
// Mostly used for testing.
func WithHTTPClient(httpClient *http.Client) ClientOption {
	return func(c *Client) {
		c.httpClient = httpClient
	}
}

// NewClient creates a new Agent Registry client.
func NewClient(ctx context.Context, projectID, location string, opts ...ClientOption) (*Client, error) {
	c := &Client{
		baseURL:   defaultBaseURL,
		projectID: projectID,
		location:  location,
	}

	for _, opt := range opts {
		opt(c)
	}

	if c.httpClient == nil {
		// Create authenticated HTTP client using Application Default Credentials
		httpClient, err := google.DefaultClient(ctx, "https://www.googleapis.com/auth/cloud-platform")
		if err != nil {
			return nil, fmt.Errorf("failed to create authenticated client: %w", err)
		}
		c.httpClient = httpClient
	}

	return c, nil
}

// Skill represents a skill resource in the Agent Registry.
type Skill struct {
	Name            string `json:"name"`
	TargetState     string `json:"targetState"`
	DefaultRevision string `json:"defaultRevision"`
}

type listSkillsResponse struct {
	Skills        []Skill `json:"skills"`
	NextPageToken string  `json:"nextPageToken"`
}

// ListAuthorizedSkills returns a list of skills in the project/location
// that are not in TARGET_STATE_DISABLED.
func (c *Client) ListAuthorizedSkills(ctx context.Context) ([]Skill, error) {
	parent := fmt.Sprintf("projects/%s/locations/%s", c.projectID, c.location)
	baseURL := fmt.Sprintf("%s/%s/skills", c.baseURL, parent)

	var allSkills []Skill
	pageToken := ""

	for {
		reqURL, err := url.Parse(baseURL)
		if err != nil {
			return nil, fmt.Errorf("invalid base URL: %w", err)
		}
		q := reqURL.Query()
		if pageToken != "" {
			q.Set("pageToken", pageToken)
		}
		reqURL.RawQuery = q.Encode()

		req, err := http.NewRequestWithContext(ctx, "GET", reqURL.String(), nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create request: %w", err)
		}

		resp, err := c.httpClient.Do(req)
		if err != nil {
			return nil, fmt.Errorf("API request failed: %w", err)
		}

		if resp.StatusCode != http.StatusOK {
			bodyBytes, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(bodyBytes))
		}

		var listResp listSkillsResponse
		err = json.NewDecoder(resp.Body).Decode(&listResp)
		resp.Body.Close()
		if err != nil {
			return nil, fmt.Errorf("failed to decode response: %w", err)
		}

		// Filter authorized skills (not DISABLED)
		for _, skill := range listResp.Skills {
			if skill.TargetState != "TARGET_STATE_DISABLED" {
				allSkills = append(allSkills, skill)
			}
		}

		if listResp.NextPageToken == "" {
			break
		}
		pageToken = listResp.NextPageToken
	}

	return allSkills, nil
}

// The skill ID provided by the caller is automatically prefixed with "private-".
func (c *Client) GetSkillContent(ctx context.Context, skillID string) (string, error) {
	// Construct the skill resource name.
	// ADR-0006 specifies: private-{skill}
	skillName := fmt.Sprintf("projects/%s/locations/%s/skills/private-%s", c.projectID, c.location, skillID)

	// First, we need to find its defaultRevision.
	skillURL := fmt.Sprintf("%s/%s", c.baseURL, skillName)
	req, err := http.NewRequestWithContext(ctx, "GET", skillURL, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create get skill request: %w", err)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to get skill: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		return "", fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(bodyBytes))
	}

	var skill Skill
	err = json.NewDecoder(resp.Body).Decode(&skill)
	resp.Body.Close()
	if err != nil {
		return "", fmt.Errorf("failed to decode skill: %w", err)
	}

	if skill.DefaultRevision == "" {
		return "", fmt.Errorf("skill %s has no default revision", skillName)
	}

	// Now fetch the revision content as a zip
	revURL := fmt.Sprintf("%s/%s?alt=media", c.baseURL, skill.DefaultRevision)
	reqRev, err := http.NewRequestWithContext(ctx, "GET", revURL, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create get revision request: %w", err)
	}

	respRev, err := c.httpClient.Do(reqRev)
	if err != nil {
		return "", fmt.Errorf("failed to get revision: %w", err)
	}
	defer respRev.Body.Close()

	if respRev.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(respRev.Body)
		return "", fmt.Errorf("API returned status %d fetching revision: %s", respRev.StatusCode, string(bodyBytes))
	}

	zipData, err := io.ReadAll(respRev.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read zip data: %w", err)
	}

	// Parse the zip
	zipReader, err := zip.NewReader(bytes.NewReader(zipData), int64(len(zipData)))
	if err != nil {
		return "", fmt.Errorf("failed to read zip archive: %w", err)
	}

	// Extract SKILL.md
	for _, f := range zipReader.File {
		if strings.HasSuffix(f.Name, "/SKILL.md") || f.Name == "SKILL.md" {
			rc, err := f.Open()
			if err != nil {
				return "", fmt.Errorf("failed to open SKILL.md from zip: %w", err)
			}
			content, err := io.ReadAll(rc)
			rc.Close()
			if err != nil {
				return "", fmt.Errorf("failed to read SKILL.md: %w", err)
			}
			return string(content), nil
		}
	}

	return "", fmt.Errorf("SKILL.md not found in revision zip")
}
