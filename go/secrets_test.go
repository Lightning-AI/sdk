package lit_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestUserSecretsAndSetSecretUseGeneratedRoutes(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/secrets":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"secrets": []map[string]any{
					{"id": "secret-1", "name": "TOKEN", "type": "SECRET_TYPE_UNSPECIFIED"},
					{"id": "secret-2", "name": "DOCKER", "type": "SECRET_TYPE_DOCKER_REGISTRY"},
				},
			})
		case "PUT /v1/secrets/secret-1":
			var body struct {
				Value string `json:"value"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode user secret update body: %v", err))
			}
			if body.Value != "updated" {
				assert.Fail(t, fmt.Sprintf("user secret value = %q, want updated", body.Value))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	u := mustUser(t, "user-1", "alice")
	secrets, err := u.Secrets()
	require.NoErrorf(t, err,
		"user.Secrets returned error")
	assert.Falsef(t, len(secrets) != 1 || secrets["TOKEN"] != "***REDACTED***",
		"unexpected user secrets: %+v", secrets)
	require.NoErrorf(t, u.SetSecret("TOKEN", "updated"),
		"user.SetSecret returned error")
	require.Errorf(t, u.SetSecret("1INVALID", "value"),
		"user.SetSecret with invalid key returned nil error")

	want := []string{
		"GET /v1/secrets",
		"GET /v1/secrets",
		"PUT /v1/secrets/secret-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceSecretsAndSetSecretUseGeneratedRoutes(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1/secrets":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"secrets": []map[string]any{
					{"id": "secret-1", "name": "TOKEN", "type": "SECRET_TYPE_UNSPECIFIED"},
				},
			})
		case "POST /v1/projects/project-1/secrets":
			var body struct {
				Name  string `json:"name"`
				Type  string `json:"type"`
				Value string `json:"value"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode teamspace secret create body: %v", err))
			}
			if body.Name != "NEW_TOKEN" || body.Type != "SECRET_TYPE_UNSPECIFIED" || body.Value != "created" {
				assert.Fail(t, fmt.Sprintf("unexpected teamspace secret create body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "default", "alice")
	secrets, err := ts.Secrets()
	require.NoErrorf(t, err,
		"teamspace.Secrets returned error")
	assert.Falsef(t, len(secrets) != 1 || secrets["TOKEN"] != "***REDACTED***",
		"unexpected teamspace secrets: %+v", secrets)
	require.NoErrorf(t, ts.SetSecret("NEW_TOKEN", "created"),
		"teamspace.SetSecret returned error")
	require.Errorf(t, ts.SetSecret("invalid-name", "value"),
		"teamspace.SetSecret with invalid key returned nil error")

	want := []string{
		"GET /v1/projects/project-1/secrets",
		"GET /v1/projects/project-1/secrets",
		"POST /v1/projects/project-1/secrets",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestUserSecretsDeleteAndTypedCollision(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/secrets":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"secrets": []map[string]any{
					{"id": "typed-secret", "name": "TOKEN", "type": "SECRET_TYPE_DOCKER_REGISTRY"},
					{"id": "generic-secret", "name": "OLD_TOKEN", "type": "SECRET_TYPE_UNSPECIFIED"},
				},
			})
		case "POST /v1/secrets":
			var body struct {
				Name  string `json:"name"`
				Value string `json:"value"`
			}
			require.NoError(t, json.NewDecoder(r.Body).Decode(&body))
			assert.Equal(t, "TOKEN", body.Name)
			assert.Equal(t, "created", body.Value)
			_ = json.NewEncoder(w).Encode(map[string]any{})
		case "DELETE /v1/secrets/generic-secret":
			_ = json.NewEncoder(w).Encode(map[string]any{})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	u := mustUser(t, "user-1", "alice")
	require.NoError(t, u.SetSecret("TOKEN", "created"))
	require.NoError(t, u.DeleteSecret("OLD_TOKEN"))
	require.ErrorContains(t, u.DeleteSecret("MISSING"), `generic user secret "MISSING" was not found`)
	require.Error(t, u.DeleteSecret("invalid-name"))

	assert.Equal(t, []string{
		"GET /v1/secrets",
		"POST /v1/secrets",
		"GET /v1/secrets",
		"DELETE /v1/secrets/generic-secret",
		"GET /v1/secrets",
	}, seen)
}

func TestTeamspaceSecretsDeleteAndTypedCollision(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1/secrets":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"secrets": []map[string]any{
					{"id": "typed-secret", "name": "TOKEN", "type": "SECRET_TYPE_HF_TOKEN"},
					{"id": "generic-secret", "name": "OLD_TOKEN", "type": "SECRET_TYPE_UNSPECIFIED"},
				},
			})
		case "POST /v1/projects/project-1/secrets":
			var body struct {
				Name  string `json:"name"`
				Type  string `json:"type"`
				Value string `json:"value"`
			}
			require.NoError(t, json.NewDecoder(r.Body).Decode(&body))
			assert.Equal(t, "TOKEN", body.Name)
			assert.Equal(t, "SECRET_TYPE_UNSPECIFIED", body.Type)
			assert.Equal(t, "created", body.Value)
			_ = json.NewEncoder(w).Encode(map[string]any{})
		case "DELETE /v1/projects/project-1/secrets/generic-secret":
			_ = json.NewEncoder(w).Encode(map[string]any{})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "default", "alice")
	require.NoError(t, ts.SetSecret("TOKEN", "created"))
	require.NoError(t, ts.DeleteSecret("OLD_TOKEN"))
	require.ErrorContains(t, ts.DeleteSecret("MISSING"), `generic teamspace secret "MISSING" was not found`)
	require.Error(t, ts.DeleteSecret("invalid-name"))

	assert.Equal(t, []string{
		"GET /v1/projects/project-1/secrets",
		"POST /v1/projects/project-1/secrets",
		"GET /v1/projects/project-1/secrets",
		"DELETE /v1/projects/project-1/secrets/generic-secret",
		"GET /v1/projects/project-1/secrets",
	}, seen)
}
