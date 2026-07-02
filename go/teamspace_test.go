package lit_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	lit "github.com/lightning-ai/sdk/go"
	"github.com/lightning-ai/sdk/go/internal/sdktest"
)

func TestTeamspaceGetWithIDUsesSimpleStruct(t *testing.T) {
	ts, err := lit.GetTeamspace("default", lit.TeamspaceOptions{ID: "project-1", Owner: testOwner{id: "user-1", name: "alice"}})
	require.NoErrorf(t, err,
		"GetTeamspace returned error")
	assert.Falsef(t, ts.ID() != "project-1" || ts.Name() != "default" || ts.Owner().Name() != "alice",
		"unexpected teamspace: %s %s %s", ts.ID(), ts.Name(), ts.Owner().Name())

}

func TestOwnerNameHandlesNilOwner(t *testing.T) {
	t.Setenv("LIGHTNING_USERNAME", "")
	t.Setenv("LIGHTNING_ORG", "")

	ts, err := lit.GetTeamspace("default", lit.TeamspaceOptions{ID: "project-1"})
	require.NoErrorf(t, err,
		"GetTeamspace returned error")
	assert.Falsef(t, ts.Owner() != nil,
		"owner = %v, want nil", ts.Owner())
	assert.Falsef(t, ts.OwnerID() != "",
		"owner ID = %q, want empty", ts.OwnerID())

}

func TestTeamspaceStringAndEqual(t *testing.T) {
	owner := testOwner{id: "user-1", name: "alice"}
	ts, err := lit.GetTeamspace("default", lit.TeamspaceOptions{ID: "project-1", Owner: owner})
	require.NoErrorf(t, err,
		"GetTeamspace returned error")

	if got, want := ts.String(), "Teamspace(name=default, owner=alice)"; got != want {
		assert.Fail(t, fmt.Sprintf("teamspace string = %q, want %q", got, want))
	}
	matching, err := lit.GetTeamspace("default", lit.TeamspaceOptions{ID: "project-1", Owner: owner})
	require.NoErrorf(t, err,
		"GetTeamspace returned error")
	assert.True(t, ts.Equal(matching),
		"matching teamspaces should be equal")

	other, err := lit.GetTeamspace("other", lit.TeamspaceOptions{ID: "project-1", Owner: owner})
	require.NoErrorf(t, err,
		"GetTeamspace returned error")
	assert.False(t, ts.Equal(other),
		"teamspaces with different names should not be equal")

}

func TestTeamspaceConnectionTypeConstantsMirrorPublicPythonAPI(t *testing.T) {
	got := []lit.ConnectionType{
		lit.ConnectionTypeEFS,
		lit.ConnectionTypeS3,
		lit.ConnectionTypeGCS,
		lit.ConnectionTypeFilestore,
	}
	want := []lit.ConnectionType{"EFS", "S3", "GCS", "FILESTORE"}
	for i := range want {
		assert.Falsef(t, got[i] != want[i],
			"connection type %d = %q, want %q", i, got[i], want[i])

	}
}

func TestTeamspaceGetUsesExplicitOwner(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/memberships":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"memberships": []map[string]any{{
					"projectId": "project-1",
					"name":      "default",
					"ownerId":   "user-1",
				}},
			})
		case "GET /v1/projects/project-1":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":      "project-1",
				"name":    "default",
				"ownerId": "user-1",
				"projectSettings": map[string]any{
					"preferredCluster":          "aws-us-east",
					"startStudioOnSpotInstance": true,
				},
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts, err := lit.GetTeamspace("default", lit.TeamspaceOptions{Owner: testOwner{id: "user-1", name: "alice"}})
	require.NoErrorf(t, err,
		"GetTeamspace returned error")
	assert.Falsef(t, ts.ID() != "project-1" || ts.Name() != "default" || ts.OwnerID() != "user-1" || ts.Owner().Name() != "alice",
		"unexpected teamspace: %+v", ts)
	assert.Falsef(t, ts.DefaultCloudAccount() != "aws-us-east" || !ts.StartStudiosOnInterruptible(),
		"unexpected teamspace settings: %+v", ts)

	want := []string{
		"GET /v1/memberships?filterByUserId=true",
		"GET /v1/projects/project-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceGetRejectsMissingName(t *testing.T) {
	_ = sdktest.NewAPIServer(t, func(w http.ResponseWriter, r *http.Request) {
		assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
	})

	_, err := lit.GetTeamspace("")
	assert.Falsef(t, err == nil || !strings.Contains(err.Error(), "teamspace requires name or ID"),
		"GetTeamspace error = %v, want name validation", err)

}

func TestTeamspaceGetRequiresResolvedOwner(t *testing.T) {
	_ = sdktest.NewAPIServer(t, func(w http.ResponseWriter, r *http.Request) {
		assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
	})
	t.Setenv("LIGHTNING_USERNAME", "")
	t.Setenv("LIGHTNING_ORG", "")

	_, err := lit.GetTeamspace("default")
	assert.Falsef(t, err == nil || !strings.Contains(err.Error(), "teamspace requires owner or ID"),
		"GetTeamspace error = %v, want owner resolution error", err)

}

func TestTeamspaceGetUsesExplicitOrgOwner(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/memberships":
			if got := r.URL.Query().Get("organizationId"); got != "org-1" {
				assert.Fail(t, fmt.Sprintf("organizationId = %q, want org-1", got))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"memberships": []map[string]any{{
					"projectId": "project-1",
					"name":      "default",
					"ownerId":   "org-1",
				}},
			})
		case "GET /v1/projects/project-1":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":      "project-1",
				"name":    "default",
				"ownerId": "org-1",
				"projectSettings": map[string]any{
					"preferredCluster": "aws-us-west",
				},
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	org, err := lit.GetOrganization("acme", lit.OrganizationOptions{ID: "org-1"})
	require.NoErrorf(t, err,
		"GetOrganization returned error")

	ts, err := lit.GetTeamspace("default", lit.TeamspaceOptions{Owner: org})
	require.NoErrorf(t, err,
		"GetTeamspace returned error")
	assert.Falsef(t, ts.ID() != "project-1" || ts.Name() != "default" || ts.OwnerID() != "org-1" || ts.Owner().Name() != "acme",
		"unexpected teamspace: %+v", ts)
	assert.Falsef(t, ts.DefaultCloudAccount() != "aws-us-west",
		"default cloud account = %q, want aws-us-west", ts.DefaultCloudAccount())

	want := []string{
		"GET /v1/memberships?filterByUserId=true&organizationId=org-1",
		"GET /v1/projects/project-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceCreateUsesExplicitOrgOwner(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects":
			var body struct {
				Name           string `json:"name"`
				OrganizationID string `json:"organizationId"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode create teamspace body: %v", err))
			}
			if body.Name != "research" || body.OrganizationID != "org-1" {
				assert.Fail(t, fmt.Sprintf("unexpected create teamspace body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":      "project-2",
				"name":    "research",
				"ownerId": "org-1",
				"projectSettings": map[string]any{
					"preferredCluster": "aws-us-east",
				},
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	org, err := lit.GetOrganization("acme", lit.OrganizationOptions{ID: "org-1"})
	require.NoErrorf(t, err,
		"GetOrganization returned error")

	ts, err := lit.CreateTeamspace("research", lit.TeamspaceOptions{Owner: org})
	require.NoErrorf(t, err,
		"CreateTeamspace returned error")
	assert.Falsef(t, ts.ID() != "project-2" || ts.Name() != "research" || ts.OwnerID() != "org-1" || ts.Owner().Name() != "acme",
		"unexpected teamspace: %+v", ts)
	assert.Falsef(t, ts.DefaultCloudAccount() != "aws-us-east",
		"default cloud account = %q, want aws-us-east", ts.DefaultCloudAccount())

	want := []string{
		"POST /v1/projects",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}
