package lit_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	lit "github.com/lightning-ai/sdk/go"
)

func filesystemTestTeamspace(t *testing.T, serverURL string) *lit.Teamspace {
	t.Helper()
	t.Setenv("LIGHTNING_CLOUD_URL", serverURL)
	t.Setenv("LIGHTNING_USER_ID", "user-1")
	t.Setenv("LIGHTNING_API_KEY", "key-1")
	ts, err := lit.GetTeamspace("default", lit.TeamspaceOptions{ID: "project-1", Owner: testOwner{id: "user-1", name: "alice"}})
	require.NoError(t, err)
	return ts
}

func TestTeamspaceListFilesFollowsCursorPages(t *testing.T) {
	var seen []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		require.Equal(t, "/v1/projects/project-1/artifacts/trees/artifacts/reports", r.URL.Path)
		if r.URL.Query().Get("cursor") == "" {
			_ = json.NewEncoder(w).Encode(map[string]any{
				"tree": []map[string]any{
					{"path": "a.txt", "type": "blob", "size": 1, "clusterId": "cluster-a", "lastModified": "2026-08-17T00:00:00Z"},
				},
				"nextCursor": "cursor-1",
			})
			return
		}
		require.Equal(t, "cursor-1", r.URL.Query().Get("cursor"))
		_ = json.NewEncoder(w).Encode(map[string]any{
			"tree": []map[string]any{
				{"path": "sub/b.txt", "type": "blob", "size": 2, "clusterId": "cluster-b"},
			},
		})
	}))
	defer server.Close()

	ts := filesystemTestTeamspace(t, server.URL)
	entries, err := ts.ListFiles("artifacts/reports", true)
	require.NoError(t, err)

	assert.Equal(t, []lit.FileEntry{
		{Path: "a.txt", Type: "blob", Size: 1, CloudAccount: "cluster-a", LastModified: "2026-08-17T00:00:00Z"},
		{Path: "sub/b.txt", Type: "blob", Size: 2, CloudAccount: "cluster-b"},
	}, entries)
	require.Len(t, seen, 2)
	assert.Contains(t, seen[0], "recursive=true")
}

func TestTeamspaceDeleteFileAndFolderUseDriveRoutes(t *testing.T) {
	var seen []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	ts := filesystemTestTeamspace(t, server.URL)
	require.NoError(t, ts.DeleteFile("artifacts/reports/a.txt"))
	require.NoError(t, ts.DeleteFolder("artifacts/reports/"))

	assert.Equal(t, []string{
		"DELETE /v1/projects/project-1/artifacts/blobs/artifacts/reports/a.txt",
		"DELETE /v1/projects/project-1/artifacts/trees/artifacts/reports",
	}, seen)
}

func TestTeamspaceDeleteRequiresRemotePath(t *testing.T) {
	ts := filesystemTestTeamspace(t, "http://127.0.0.1:0")
	assert.Error(t, ts.DeleteFile(""))
	assert.Error(t, ts.DeleteFolder("/"))
}
