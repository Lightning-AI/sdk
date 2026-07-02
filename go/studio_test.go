package lit_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	lit "github.com/gridai/lightning-sdk/go"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestStudioGetWithIDUsesSimpleStruct(t *testing.T) {
	s, err := lit.GetStudio("dev", lit.StudioOptions{ID: "studio-1", Teamspace: mustTeamspace(t, "project-1", "default", "alice")})
	require.NoErrorf(t, err,
		"GetStudio returned error")
	assert.Falsef(t, s.ID() != "studio-1" || s.Name() != "dev" || s.TeamspaceID() != "project-1",
		"unexpected studio: %s %s %s", s.ID(), s.Name(), s.TeamspaceID())

}

func TestStudioStringAndEqual(t *testing.T) {
	ts := mustTeamspace(t, "project-1", "default", "alice")
	s, err := lit.GetStudio("dev", lit.StudioOptions{ID: "studio-1", Teamspace: ts})
	require.NoErrorf(t, err,
		"GetStudio returned error")

	if got, want := s.String(), "Studio(name=dev, teamspace=Teamspace(name=default, owner=alice))"; got != want {
		assert.Fail(t, fmt.Sprintf("studio string = %q, want %q", got, want))
	}
	matching, err := lit.GetStudio("dev", lit.StudioOptions{ID: "studio-1", Teamspace: ts})
	require.NoErrorf(t, err,
		"GetStudio returned error")
	assert.True(t, s.Equal(matching),
		"matching studios should be equal")

	other, err := lit.GetStudio("dev", lit.StudioOptions{ID: "studio-2", Teamspace: mustTeamspace(t, "project-2", "default", "alice")})
	require.NoErrorf(t, err,
		"GetStudio returned error")
	assert.False(t, s.Equal(other),
		"studios in different teamspaces should not be equal")

}

func TestStudioGetUsesExplicitTeamspace(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/users/-/projects/-/cloudspaces/dev/getbyname",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		if got := r.URL.Query().Get("projectId"); got != "project-1" {
			assert.Fail(t, fmt.Sprintf("projectId = %q, want project-1", got))
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"cloudspace": map[string]any{
				"id":        "studio-1",
				"name":      "dev",
				"projectId": "project-1",
				"clusterId": "aws-us-east",
			},
			"project": map[string]any{
				"id":   "project-1",
				"name": "default",
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Setenv("LIGHTNING_USERNAME", "")
	t.Setenv("LIGHTNING_ORG", "")
	t.Setenv("LIGHTNING_TEAMSPACE", "")

	s, err := lit.GetStudio("dev", lit.StudioOptions{Teamspace: mustTeamspace(t, "project-1", "")})
	require.NoErrorf(t, err,
		"GetStudio returned error")
	assert.Falsef(t, s.ID() != "studio-1" || s.Name() != "dev" || s.TeamspaceID() != "project-1" || s.Teamspace() != "default" || s.Cloud() != "aws-us-east",
		"unexpected studio: %+v", s)

	want := []string{"GET /v1/users/-/projects/-/cloudspaces/dev/getbyname?projectId=project-1"}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioCreateUsesExplicitTeamspace(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects/project-1/cloudspaces":
			var body struct {
				ClusterID   string `json:"clusterId"`
				ComputeName string `json:"computeName"`
				DisplayName string `json:"displayName"`
				Name        string `json:"name"`
				Spot        bool   `json:"spot"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode create studio body: %v", err))
			}
			if body.Name != "dev" || body.DisplayName != "dev" || body.ComputeName != "gpu" || body.ClusterID != "aws-us-east" || !body.Spot {
				assert.Fail(t, fmt.Sprintf("unexpected create studio body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "studio-1",
				"name":      "dev",
				"projectId": "project-1",
				"clusterId": "aws-us-east",
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	interruptible := true
	s, err := lit.CreateStudio(
		"dev",
		lit.StudioOptions{Teamspace: mustTeamspace(t, "project-1", "default", "alice"), Cloud: "aws-us-east", Machine: "gpu", Interruptible: &interruptible},
	)
	require.NoErrorf(t, err,
		"CreateStudio returned error")
	assert.Falsef(t, s.ID() != "studio-1" || s.Name() != "dev" || s.TeamspaceID() != "project-1" || s.Teamspace() != "default" || s.OwnerName() != "alice",
		"unexpected studio: %+v", s)

	want := []string{
		"POST /v1/projects/project-1/cloudspaces",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioStartUsesTeamspaceInterruptibleDefault(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":   "project-1",
				"name": "default",
				"projectSettings": map[string]any{
					"startStudioOnSpotInstance": true,
				},
			})
		case "POST /v1/projects/project-1/cloudspaces/studio-1/start":
			var body struct {
				ComputeConfig struct {
					Name string `json:"name"`
					Spot bool   `json:"spot"`
				} `json:"computeConfig"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode start studio body: %v", err))
			}
			if body.ComputeConfig.Name != "CPU" || !body.ComputeConfig.Spot {
				assert.Fail(t, fmt.Sprintf("unexpected start studio body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s, err := lit.GetStudio("dev", lit.StudioOptions{ID: "studio-1", Teamspace: mustTeamspace(t, "project-1", "")})
	require.NoErrorf(t, err,
		"GetStudio returned error")
	require.NoErrorf(t, s.Start(),
		"studio.Start returned error")
	assert.Truef(t, s.Interruptible(),
		"studio interruptible = false, want true")

	want := []string{
		"GET /v1/projects/project-1",
		"POST /v1/projects/project-1/cloudspaces/studio-1/start",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioStartMapsStartOptions(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodPost || r.URL.Path != "/v1/projects/project-1/cloudspaces/studio-1/start",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		var body struct {
			ComputeConfig struct {
				Name                        string `json:"name"`
				RequestedRunDurationSeconds string `json:"requestedRunDurationSeconds"`
				Spot                        bool   `json:"spot"`
			} `json:"computeConfig"`
		}
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode start studio body")
		assert.Falsef(t, body.ComputeConfig.Name != "gpu" || body.ComputeConfig.RequestedRunDurationSeconds != "7200" || body.ComputeConfig.Spot,
			"unexpected start studio body: %+v", body)

		_ = json.NewEncoder(w).Encode(map[string]any{})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	initialInterruptible := true
	s, err := lit.GetStudio("dev", lit.StudioOptions{ID: "studio-1", Teamspace: mustTeamspace(t, "project-1", ""), Machine: "CPU", Interruptible: &initialInterruptible})
	require.NoErrorf(t, err,
		"GetStudio returned error")

	interruptible := false
	require.NoErrorf(t, s.Start(
		lit.StartStudioOptions{Machine: "gpu", Interruptible: &interruptible, MaxRuntime: 7200},
	),
		"studio.Start returned error")
	assert.Falsef(t, s.Machine() != "gpu" || s.Interruptible(),
		"unexpected studio after start: %+v", s)

	want := []string{"POST /v1/projects/project-1/cloudspaces/studio-1/start"}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioCreateRejectsMissingTeamspace(t *testing.T) {
	_, err := lit.CreateStudio("dev")
	assert.Falsef(t, err == nil || err.Error() != "studio create requires teamspace",
		"CreateStudio error = %v, want teamspace validation", err)

}
