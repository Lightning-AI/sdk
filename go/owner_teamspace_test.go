package lit_test

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	lit "github.com/lightning-ai/sdk/go"
)

var (
	_ lit.Owner = (*lit.User)(nil)
	_ lit.Owner = (*lit.Organization)(nil)
)

func TestOwnersListTeamspacesFromMemberships(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/memberships",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())
		assert.Falsef(t, r.URL.Query().Get("filterByUserId") != "true",
			"filterByUserId = %q, want true", r.URL.Query().Get("filterByUserId"))

		switch r.URL.Query().Get("organizationId") {
		case "":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"memberships": []map[string]any{
					{"projectId": "project-1", "name": "default", "ownerId": "user-1"},
					{"projectId": "project-2", "name": "other", "ownerId": "org-1"},
				},
			})
		case "org-1":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"memberships": []map[string]any{
					{"projectId": "project-2", "name": "other", "ownerId": "org-1"},
					{"projectId": "project-3", "name": "not-owned", "ownerId": "org-2"},
				},
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected organizationId: %s", r.URL.Query().Get("organizationId")))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	u := mustUser(t, "user-1", "alice")
	userTeamspaces, err := u.Teamspaces()
	require.NoErrorf(t, err,
		"user.Teamspaces returned error")
	assert.Falsef(t, len(userTeamspaces) != 1 || userTeamspaces[0].ID() != "project-1" || userTeamspaces[0].Owner().Name() != "alice",
		"unexpected user teamspaces: %+v", userTeamspaces)

	o := mustOrg(t, "org-1", "acme")
	orgTeamspaces, err := o.Teamspaces()
	require.NoErrorf(t, err,
		"org.Teamspaces returned error")
	assert.Falsef(t, len(orgTeamspaces) != 1 || orgTeamspaces[0].ID() != "project-2" || orgTeamspaces[0].Owner().Name() != "acme",
		"unexpected org teamspaces: %+v", orgTeamspaces)
	assert.Falsef(t, len(seen) != 2,
		"seen requests = %v, want 2 requests", seen)

}

func TestUserOrganizationsUsesGeneratedRoute(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/orgs",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		_ = json.NewEncoder(w).Encode(map[string]any{
			"organizations": []map[string]any{
				{"id": "org-1", "name": "acme", "preferredCluster": "cloud-1"},
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	u := mustUser(t, "user-1", "alice")
	organizations, err := u.Organizations()
	require.NoErrorf(t, err,
		"user.Organizations returned error")
	assert.Falsef(t, len(organizations) != 1 || organizations[0].ID() != "org-1" || organizations[0].Name() != "acme" || organizations[0].DefaultCloudAccount() != "cloud-1",
		"unexpected organizations: %+v", organizations)

	want := []string{"GET /v1/orgs"}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceListsStudiosJobsAndMMTs(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1/cloudspaces":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"cloudspaces": []map[string]any{
					{"id": "studio-1", "name": "dev", "projectId": "project-1", "clusterId": "cloud-1", "state": "CLOUD_SPACE_STATE_READY"},
				},
			})
		case "GET /v1/projects/project-1/jobs":
			if r.URL.Query().Get("standalone") != "true" {
				assert.Fail(t, fmt.Sprintf("standalone = %q, want true", r.URL.Query().Get("standalone")))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"jobs": []map[string]any{
					{
						"id":        "job-1",
						"name":      "train",
						"projectId": "project-1",
						"state":     "running",
						"totalCost": 3.5,
						"spec": map[string]any{
							"cloudspaceId": "studio-1",
							"command":      "python train.py",
							"image":        "ubuntu:22.04",
							"instanceName": "cpu",
						},
					},
				},
			})
		case "GET /v1/projects/project-1/multi-machine-jobs":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"multiMachineJobs": []map[string]any{
					{
						"id":        "mmt-1",
						"name":      "dist-train",
						"projectId": "project-1",
						"machines":  4,
						"state":     "running",
						"totalCost": 11.25,
						"spec": map[string]any{
							"cloudspaceId": "studio-1",
							"command":      "torchrun train.py",
							"image":        "pytorch/pytorch:latest",
							"instanceName": "gpu",
						},
					},
				},
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "default", "alice")

	studios, err := ts.Studios()
	require.NoErrorf(t, err,
		"teamspace.Studios returned error")
	assert.Falsef(t, len(studios) != 1 || studios[0].ID() != "studio-1" || studios[0].Cloud() != "cloud-1" || studios[0].Status() != "CLOUD_SPACE_STATE_READY",
		"unexpected studios: %+v", studios)

	jobs, err := ts.Jobs()
	require.NoErrorf(t, err,
		"teamspace.Jobs returned error")
	assert.Falsef(t, len(jobs) != 1 || jobs[0].ID() != "job-1" || jobs[0].StudioID() != "studio-1" || jobs[0].Machine() != "cpu" || jobs[0].TotalCost() != 3.5,
		"unexpected jobs: %+v", jobs)

	if got, want := jobs[0].Link(), "https://lightning.ai/alice/default/jobs/train?app_id=jobs"; got != want {
		assert.Fail(t, fmt.Sprintf("job link = %q, want %q", got, want))
	}

	mmts, err := ts.MMTs()
	require.NoErrorf(t, err,
		"teamspace.MMTs returned error")
	assert.Falsef(t, len(mmts) != 1 || mmts[0].ID() != "mmt-1" || mmts[0].NumMachines() != 4 || mmts[0].Machine() != "gpu" || mmts[0].TotalCost() != 11.25,
		"unexpected mmts: %+v", mmts)

	if got, want := mmts[0].Link(), "https://lightning.ai/alice/default/jobs/dist-train?app_id=mmt"; got != want {
		assert.Fail(t, fmt.Sprintf("mmt link = %q, want %q", got, want))
	}

	want := []string{
		"GET /v1/projects/project-1/cloudspaces",
		"GET /v1/projects/project-1/jobs?standalone=true",
		"GET /v1/projects/project-1/multi-machine-jobs",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceRefreshAndCloudAccountsUseGeneratedRoutes(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":      "project-1",
				"name":    "default",
				"ownerId": "user-1",
				"projectSettings": map[string]any{
					"preferredCluster":          "cloud-1",
					"startStudioOnSpotInstance": true,
				},
			})
		case "GET /v1/projects/project-1/projectclustersbindings":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"clusters": []map[string]any{
					{"clusterId": "cloud-1", "clusterName": "Lightning", "clusterRegion": "us-east-1", "isClusterHealthy": true},
				},
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "")
	require.NoErrorf(t, ts.Refresh(),
		"teamspace.Refresh returned error")
	assert.Falsef(t, ts.Name() != "default" || ts.DefaultCloudAccount() != "cloud-1" || !ts.StartStudiosOnInterruptible(),
		"unexpected refreshed teamspace: %+v", ts)

	accounts, err := ts.CloudAccounts()
	require.NoErrorf(t, err,
		"teamspace.CloudAccounts returned error")
	assert.Falsef(t, len(accounts) != 1 || accounts[0] != "Lightning",
		"unexpected cloud accounts: %+v", accounts)

	names, err := ts.CloudAccountNames()
	require.NoErrorf(t, err,
		"teamspace.CloudAccountNames returned error")
	assert.Falsef(t, len(names) != 1 || names[0] != "Lightning",
		"unexpected cloud account names: %+v", names)

	clusters, err := ts.Clusters()
	require.NoErrorf(t, err,
		"teamspace.Clusters returned error")
	assert.Falsef(t, len(clusters) != 1 || clusters[0] != "Lightning",
		"unexpected clusters: %+v", clusters)

	want := []string{
		"GET /v1/projects/project-1",
		"GET /v1/projects/project-1/projectclustersbindings",
		"GET /v1/projects/project-1/projectclustersbindings",
		"GET /v1/projects/project-1/projectclustersbindings",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceDownloadFileUsesArtifactBlobRoute(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/projects/project-1/artifacts/blobs/drive/remote.txt",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		query := r.URL.Query()
		assert.Falsef(t, query.Get("clusterId") != "cloud-1" || query.Get("token") != "token-1",
			"unexpected query: %s", r.URL.RawQuery)

		_, _ = w.Write([]byte("teamspace contents"))
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Setenv("LIGHTNING_AUTH_TOKEN", "token-1")

	targetPath := filepath.Join(t.TempDir(), "downloaded.txt")
	ts := mustTeamspace(t, "project-1", "")
	require.NoErrorf(t, ts.DownloadFile("drive/remote.txt", targetPath, "cloud-1"),
		"teamspace.DownloadFile returned error")

	got, err := os.ReadFile(targetPath)
	require.NoErrorf(t, err,
		"read downloaded file")
	assert.Falsef(t, string(got) != "teamspace contents",
		"downloaded file = %q, want teamspace contents", string(got))

}

func TestTeamspaceDownloadFolderUsesRecursiveTree(t *testing.T) {
	var seen []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1/artifacts/trees/drive":
			query := r.URL.Query()
			if query.Get("clusterId") != "cloud-1" || query.Get("recursive") != "true" || query.Get("token") != "token-1" {
				assert.Fail(t, fmt.Sprintf("unexpected tree query: %s", r.URL.RawQuery))
			}
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"tree": []map[string]any{
					{"path": "a.txt", "type": "blob", "size": 1},
					{"path": "nested", "type": "tree"},
					{"path": "nested/b.txt", "type": "blob", "size": 1},
				},
			})
		case "GET /v1/projects/project-1/artifacts/blobs/drive/a.txt":
			query := r.URL.Query()
			if query.Get("clusterId") != "cloud-1" || query.Get("token") != "token-1" {
				assert.Fail(t, fmt.Sprintf("unexpected download query: %s", r.URL.RawQuery))
			}
			_, _ = w.Write([]byte("a"))
		case "GET /v1/projects/project-1/artifacts/blobs/drive/nested/b.txt":
			query := r.URL.Query()
			if query.Get("clusterId") != "cloud-1" || query.Get("token") != "token-1" {
				assert.Fail(t, fmt.Sprintf("unexpected download query: %s", r.URL.RawQuery))
			}
			_, _ = w.Write([]byte("b"))
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Setenv("LIGHTNING_AUTH_TOKEN", "token-1")

	targetDir := t.TempDir()
	ts := mustTeamspace(t, "project-1", "")
	require.NoErrorf(t, ts.DownloadFolder("drive", targetDir, "cloud-1"),
		"teamspace.DownloadFolder returned error")

	gotA, err := os.ReadFile(filepath.Join(targetDir, "a.txt"))
	require.NoErrorf(t, err,
		"read a.txt")

	gotB, err := os.ReadFile(filepath.Join(targetDir, "nested", "b.txt"))
	require.NoErrorf(t, err,
		"read nested/b.txt")
	assert.Falsef(t, string(gotA) != "a" || string(gotB) != "b",
		"downloaded files = (%q, %q), want (a, b)", string(gotA), string(gotB))

	want := []string{
		"GET /v1/projects/project-1/artifacts/trees/drive?clusterId=cloud-1&recursive=true&token=token-1",
		"GET /v1/projects/project-1/artifacts/blobs/drive/a.txt?clusterId=cloud-1&token=token-1",
		"GET /v1/projects/project-1/artifacts/blobs/drive/nested/b.txt?clusterId=cloud-1&token=token-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceUploadFileUsesArtifactBlobRoute(t *testing.T) {
	var seen []string
	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects/project-1/artifacts/blobs":
			if token := r.URL.Query().Get("token"); token != "token-1" {
				assert.Fail(t, fmt.Sprintf("token = %q, want token-1", token))
			}
			// the cluster travels in the body, not the query
			clusterID, paths := decodeBlobUploadBatch(t, r)
			assert.Falsef(t, clusterID != "cloud-1" || len(paths) != 1 || paths[0] != "drive/remote.txt",
				"unexpected upload request: cluster_id=%q paths=%v", clusterID, paths)
			writeBlobUploadResponse(w, "drive/remote.txt", server.URL+"/signed/drive/remote.txt", nil)
		case "PUT /signed/drive/remote.txt":
			assert.Falsef(t, r.Header.Get("Authorization") != "",
				"presigned PUT must not carry credentials")
			body, err := io.ReadAll(r.Body)
			assert.NoErrorf(t, err,
				"read upload body")
			assert.Falsef(t, err == nil && string(body) != "teamspace upload",
				"upload body = %q, want teamspace upload", string(body))
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Setenv("LIGHTNING_AUTH_TOKEN", "token-1")

	sourcePath := filepath.Join(t.TempDir(), "source.txt")
	require.NoErrorf(t, os.WriteFile(sourcePath, []byte("teamspace upload"), 0o600),
		"write source file")

	ts := mustTeamspace(t, "project-1", "")
	require.NoErrorf(t, ts.UploadFile(sourcePath, "drive/remote.txt", "cloud-1"),
		"teamspace.UploadFile returned error")

	// single-part teamspace uploads don't need finalizing, so no complete call
	want := []string{
		"POST /v1/projects/project-1/artifacts/blobs?token=token-1",
		"PUT /signed/drive/remote.txt",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceUploadFolderPreservesRelativePaths(t *testing.T) {
	var seen []string
	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects/project-1/artifacts/blobs":
			if token := r.URL.Query().Get("token"); token != "token-1" {
				assert.Fail(t, fmt.Sprintf("token = %q, want token-1", token))
			}
			clusterID, paths := decodeBlobUploadBatch(t, r)
			// non-fatal on the handler goroutine; a 400 fails fast (not retried)
			if len(paths) != 1 {
				assert.Failf(t, "unexpected upload paths", "%v", paths)
				http.Error(w, "expected exactly one blob", http.StatusBadRequest)
				return
			}
			assert.Falsef(t, clusterID != "cloud-1",
				"cluster_id = %q, want cloud-1", clusterID)
			writeBlobUploadResponse(w, paths[0], server.URL+"/signed/"+paths[0], nil)
		case "PUT /signed/drive/a.txt", "PUT /signed/drive/nested/b.txt":
			// presigned storage PUT
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Setenv("LIGHTNING_AUTH_TOKEN", "token-1")

	sourceDir := t.TempDir()
	require.NoErrorf(t, os.WriteFile(filepath.Join(sourceDir, "a.txt"), []byte("a"), 0o600),
		"write a.txt")
	require.NoErrorf(t, os.Mkdir(filepath.Join(sourceDir, "nested"), 0o755),
		"mkdir nested")
	require.NoErrorf(t, os.WriteFile(filepath.Join(sourceDir, "nested", "b.txt"), []byte("b"), 0o600),
		"write nested/b.txt")

	ts := mustTeamspace(t, "project-1", "")
	require.NoErrorf(t, ts.UploadFolder(sourceDir, "drive", "cloud-1"),
		"teamspace.UploadFolder returned error")

	want := []string{
		"POST /v1/projects/project-1/artifacts/blobs?token=token-1",
		"PUT /signed/drive/a.txt",
		"POST /v1/projects/project-1/artifacts/blobs?token=token-1",
		"PUT /signed/drive/nested/b.txt",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceGetFolderUsesDataConnectionRoute(t *testing.T) {
	var body map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Falsef(t, r.Method != http.MethodPost || r.URL.Path != "/v1/projects/project-1/data-connections",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode request body")

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"id": "connection-1"})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "")
	require.NoErrorf(t, ts.NewFolder("datasets"),
		"teamspace.NewFolder returned error")
	assert.Falsef(t, body["name"] != "datasets" || body["createResources"] != true || body["force"] != true || body["writable"] != true,
		"unexpected new folder body: %#v", body)

	r2, ok := body["r2"].(map[string]any)
	assert.Falsef(t, !ok || r2["name"] != "datasets",
		"r2 body = %#v, want name datasets", body["r2"])

	if _, ok := body["clusterId"]; ok {
		assert.Fail(t, fmt.Sprintf("clusterId should be omitted for cloud-agnostic folders: %#v", body))
	}
}

func TestTeamspaceGetFolderCreatesAWSFolderOnCloudAccount(t *testing.T) {
	var body map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Falsef(t, r.Method != http.MethodPost || r.URL.Path != "/v1/projects/project-1/data-connections",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode request body")

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"id": "connection-1"})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "")
	require.NoErrorf(t, ts.NewFolder(
		"datasets",
		lit.FolderOptions{Location: lit.FolderLocationAWS, Cloud: "cloud-1"},
	),
		"teamspace.NewFolder returned error")
	assert.Falsef(t, body["name"] != "datasets" || body["createResources"] != true || body["force"] != true || body["writable"] != true,
		"unexpected new folder body: %#v", body)
	assert.Falsef(t, body["clusterId"] != "cloud-1",
		"clusterId = %#v, want cloud-1", body["clusterId"])

	accessClusterIDs, ok := body["accessClusterIds"].([]any)
	assert.Falsef(t, !ok || len(accessClusterIDs) != 1 || accessClusterIDs[0] != "cloud-1",
		"accessClusterIds = %#v, want [cloud-1]", body["accessClusterIds"])

	if _, ok := body["s3Folder"].(map[string]any); !ok {
		assert.Fail(t, fmt.Sprintf("s3Folder = %#v, want object", body["s3Folder"]))
	}
	if _, ok := body["r2"]; ok {
		assert.Fail(t, fmt.Sprintf("r2 should be omitted for AWS folders: %#v", body))
	}
}

func TestTeamspaceGetConnectionCreatesReadOnlyEFSConnection(t *testing.T) {
	var body map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Falsef(t, r.Method != http.MethodPost || r.URL.Path != "/v1/projects/project-1/data-connections",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode request body")

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"id": "connection-1"})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "")
	writable := false
	require.NoErrorf(t, ts.NewConnection(
		"efs-data",
		"fs-123",
		lit.ConnectionTypeEFS,
		lit.ConnectionOptions{Cloud: "cloud-1", Region: "us-east-1", Writable: &writable},
	),
		"teamspace.NewConnection returned error")
	assert.Falsef(t, body["name"] != "efs-data" || body["createResources"] != false || body["force"] != true || body["writable"] != false,
		"unexpected new connection body: %#v", body)
	assert.Falsef(t, body["clusterId"] != "cloud-1",
		"clusterId = %#v, want cloud-1", body["clusterId"])

	accessClusterIDs, ok := body["accessClusterIds"].([]any)
	assert.Falsef(t, !ok || len(accessClusterIDs) != 1 || accessClusterIDs[0] != "cloud-1",
		"accessClusterIds = %#v, want [cloud-1]", body["accessClusterIds"])

	efs, ok := body["efs"].(map[string]any)
	assert.Falsef(t, !ok || efs["fileSystemId"] != "fs-123" || efs["region"] != "us-east-1",
		"efs body = %#v, want fileSystemId fs-123 and region us-east-1", body["efs"])

}

func TestTeamspaceListMachinesUsesBoundCloudAccounts(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1/projectclustersbindings":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"clusters": []map[string]any{
					{"clusterId": "cloud-1", "clusterName": "Lightning", "clusterRegion": "us-east-1", "isClusterHealthy": true},
					{"clusterId": "cloud-2", "clusterName": "Backup", "clusterRegion": "us-west-2", "isClusterHealthy": true},
				},
			})
		case "GET /v1/projects/project-1/clusters/cloud-1/accelerators":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"accelerator": []map[string]any{
					{
						"instanceId":             "g5.2xlarge",
						"slugMultiCloud":         "A10G x 1",
						"family":                 "A10G",
						"cost":                   1.5,
						"spotPrice":              0.7,
						"provider":               "AWS",
						"availableInSeconds":     "60",
						"availableInSecondsSpot": "120",
						"resources": map[string]any{
							"gpu": 1,
						},
					},
					{
						"instanceId":     "p4d.24xlarge",
						"slugMultiCloud": "A100 x 8",
						"family":         "A100",
						"outOfCapacity":  true,
						"resources": map[string]any{
							"gpu": 8,
						},
					},
				},
			})
		case "GET /v1/projects/project-1/clusters/cloud-2/accelerators":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"accelerator": []map[string]any{
					{
						"instanceId":     "cpu-small",
						"slugMultiCloud": "CPU x 2",
						"family":         "CPU",
						"provider":       "GCP",
						"resources": map[string]any{
							"cpu": 2,
						},
					},
				},
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "default")
	machines, err := ts.ListMachines("", "")
	require.NoErrorf(t, err,
		"teamspace.ListMachines returned error")
	assert.Falsef(t, len(machines) != 2,
		"machines = %+v, want 2 available machines", machines)
	assert.Falsef(t, machines[0] != lit.MachineA10G,
		"unexpected gpu machine: %+v", machines[0])
	assert.Falsef(t, machines[1] != lit.MachineCPUX2,
		"unexpected cpu machine: %+v", machines[1])

	want := []string{
		"GET /v1/projects/project-1/projectclustersbindings",
		"GET /v1/projects/project-1/clusters/cloud-1/accelerators",
		"GET /v1/projects/project-1/clusters/cloud-2/accelerators",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceListMachinesUsesExplicitCloudAccount(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/projects/project-1/clusters/cloud-1/accelerators",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		_ = json.NewEncoder(w).Encode(map[string]any{
			"accelerator": []map[string]any{
				{
					"instanceId":     "g5.2xlarge",
					"slugMultiCloud": "A10G x 1",
					"family":         "A10G",
					"provider":       "AWS",
					"resources": map[string]any{
						"gpu": 1,
					},
				},
				{
					"instanceId":     "cpu-small",
					"slugMultiCloud": "CPU x 2",
					"family":         "CPU",
					"provider":       "AWS",
					"resources": map[string]any{
						"cpu": 2,
					},
				},
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "default")
	machines, err := ts.ListMachines("cloud-1", lit.MachineA10G)
	require.NoErrorf(t, err,
		"teamspace.ListMachines returned error")
	assert.Falsef(t, len(machines) != 1 || machines[0] != lit.MachineA10G,
		"unexpected filtered machines: %+v", machines)

	want := []string{"GET /v1/projects/project-1/clusters/cloud-1/accelerators"}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceListMachinesUsesCloudProvider(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1/projectclustersbindings":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"clusters": []map[string]any{
					{"clusterId": "cloud-1", "clusterName": "Lightning"},
				},
			})
		case "GET /v1/projects/project-1/clusters/cloud-1/accelerators":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"accelerator": []map[string]any{
					{
						"instanceId":     "g5.2xlarge",
						"slugMultiCloud": "A10G x 1",
						"family":         "A10G",
						"provider":       "AWS",
						"resources": map[string]any{
							"gpu": 1,
						},
					},
					{
						"instanceId":     "cpu-small",
						"slugMultiCloud": "CPU x 2",
						"family":         "CPU",
						"provider":       "GCP",
						"resources": map[string]any{
							"cpu": 2,
						},
					},
				},
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "default")
	machines, err := ts.ListMachines("aws", "")
	require.NoErrorf(t, err,
		"teamspace.ListMachines returned error")
	assert.Falsef(t, len(machines) != 1 || machines[0] != lit.MachineA10G,
		"unexpected provider-filtered machines: %+v", machines)

	want := []string{
		"GET /v1/projects/project-1/projectclustersbindings",
		"GET /v1/projects/project-1/clusters/cloud-1/accelerators",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestTeamspaceListMachinesTranslatesInstanceTypesToPublicMachines(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/projects/project-1/clusters/cloud-1/accelerators",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		_ = json.NewEncoder(w).Encode(map[string]any{
			"accelerator": []map[string]any{
				{
					"instanceId":          "g6e.xlarge",
					"secondaryInstanceId": "g6e-custom",
					"family":              "L4",
					"provider":            "AWS",
					"resources": map[string]any{
						"gpu": 1,
					},
				},
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "default")
	machines, err := ts.ListMachines("cloud-1", "")
	require.NoErrorf(t, err,
		"teamspace.ListMachines returned error")
	assert.Falsef(t, len(machines) != 1 || machines[0] != lit.MachineL4,
		"unexpected translated machines: %+v", machines)

	want := []string{"GET /v1/projects/project-1/clusters/cloud-1/accelerators"}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}
