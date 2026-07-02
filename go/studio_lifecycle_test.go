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
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	lit "github.com/lightning-ai/sdk/go"
)

func TestStudioCreateStartStopAndDeleteUseGeneratedRoutes(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects/project-1/cloudspaces":
			var body struct {
				Name        string `json:"name"`
				DisplayName string `json:"displayName"`
				ClusterID   string `json:"clusterId"`
				ComputeName string `json:"computeName"`
				Spot        bool   `json:"spot"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode create body: %v", err))
			}
			if body.Name != "dev" || body.DisplayName != "dev" || body.ClusterID != "cloud-1" || body.ComputeName != "cpu" || !body.Spot {
				assert.Fail(t, fmt.Sprintf("unexpected create body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "studio-1",
				"name":      "dev",
				"projectId": "project-1",
				"clusterId": "cloud-1",
				"state":     "CLOUD_SPACE_STATE_READY",
			})
		case "POST /v1/projects/project-1/cloudspaces/studio-1/start":
			var body struct {
				ComputeConfig struct {
					Name            string `json:"name"`
					ClusterOverride string `json:"clusterOverride"`
					Spot            bool   `json:"spot"`
				} `json:"computeConfig"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode start body: %v", err))
			}
			if body.ComputeConfig.Name != "cpu" || body.ComputeConfig.ClusterOverride != "cloud-1" || !body.ComputeConfig.Spot {
				assert.Fail(t, fmt.Sprintf("unexpected start body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{})
		case "POST /v1/projects/project-1/cloudspaces/studio-1/stop":
			_ = json.NewEncoder(w).Encode(map[string]any{})
		case "DELETE /v1/projects/project-1/cloudspaces/studio-1":
			_ = json.NewEncoder(w).Encode(map[string]any{})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	interruptible := true
	s, err := lit.CreateStudio("dev",
		lit.StudioOptions{Teamspace: mustTeamspace(t, "project-1", ""), Cloud: "cloud-1", Machine: "cpu", Interruptible: &interruptible},
	)
	require.NoErrorf(t, err,
		"studio.Create returned error")
	assert.Falsef(t, s.ID() != "studio-1" || s.Status() != "CLOUD_SPACE_STATE_READY" || s.Cloud() != "cloud-1",
		"unexpected studio: %+v", s)
	require.NoErrorf(t, s.Start(),
		"studio.Start returned error")
	assert.Falsef(t, s.Status() != "running",
		"studio status after start = %q, want running", s.Status())
	require.NoErrorf(t, s.Stop(),
		"studio.Stop returned error")
	assert.Falsef(t, s.Status() != "stopped",
		"studio status after stop = %q, want stopped", s.Status())
	require.NoErrorf(t, s.Delete(),
		"studio.Delete returned error")

	want := []string{
		"POST /v1/projects/project-1/cloudspaces",
		"POST /v1/projects/project-1/cloudspaces/studio-1/start",
		"POST /v1/projects/project-1/cloudspaces/studio-1/stop",
		"DELETE /v1/projects/project-1/cloudspaces/studio-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioStartUsesDefaultMachineAndInterruptibleOverride(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodPost || r.URL.Path != "/v1/projects/project-1/cloudspaces/studio-1/start",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		var body struct {
			ComputeConfig struct {
				Name            string `json:"name"`
				ClusterOverride string `json:"clusterOverride"`
				Spot            bool   `json:"spot"`
			} `json:"computeConfig"`
		}
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode start body")
		assert.Falsef(t, body.ComputeConfig.Name != "CPU" || body.ComputeConfig.ClusterOverride != "cloud-1" || !body.ComputeConfig.Spot,
			"unexpected start body: %+v", body.ComputeConfig)

		_ = json.NewEncoder(w).Encode(map[string]any{})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Setenv("LIGHTNING_INTERRUPTIBLE_OVERRIDE", "true")

	s := mustStudio(t, "studio-1", "project-1", lit.StudioOptions{Cloud: "cloud-1"})
	require.NoErrorf(t, s.Start(),
		"studio.Start returned error")
	assert.Falsef(t, s.Status() != "running" || s.Machine() != "CPU" || !s.Interruptible(),
		"unexpected started studio: %+v", s)

}

func TestStudioRenameUsesUpdateCloudSpaceRoute(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodPut || r.URL.Path != "/v1/projects/project-1/cloudspaces/studio-1",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		var body struct {
			DisplayName string `json:"displayName"`
		}
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode rename body")
		assert.Falsef(t, body.DisplayName != "dev-renamed",
			"displayName = %q, want dev-renamed", body.DisplayName)

		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":        "studio-1",
			"name":      "dev-renamed",
			"projectId": "project-1",
			"state":     "CLOUD_SPACE_STATE_READY",
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s, err := lit.GetStudio("dev", lit.StudioOptions{ID: "studio-1", Teamspace: mustTeamspace(t, "project-1", "")})
	require.NoErrorf(t, err,
		"studio.New returned error")
	require.NoErrorf(t, s.Rename("dev-renamed"),
		"studio.Rename returned error")
	assert.Falsef(t, s.Name() != "dev-renamed" || s.Status() != "CLOUD_SPACE_STATE_READY",
		"unexpected renamed studio: %+v", s)

	want := []string{"PUT /v1/projects/project-1/cloudspaces/studio-1"}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioPublicIPUsesInstanceStatusRoute(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/projects/project-1/cloudspaces/studio-1/codestatus",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		_ = json.NewEncoder(w).Encode(map[string]any{
			"inUse": map[string]any{
				"publicIpAddress": "203.0.113.10",
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s := mustStudio(t, "studio-1", "project-1")
	publicIP, err := s.PublicIP()
	require.NoErrorf(t, err,
		"studio.PublicIP returned error")
	assert.Falsef(t, publicIP != "203.0.113.10",
		"publicIP = %q, want 203.0.113.10", publicIP)

	want := []string{"GET /v1/projects/project-1/cloudspaces/studio-1/codestatus"}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioDownloadFileUsesArtifactBlobRoute(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote.txt",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		query := r.URL.Query()
		assert.Falsef(t, query.Get("clusterId") != "cloud-1" || query.Get("key") != "/cloudspaces/studio-1/code/content/remote.txt" || query.Get("token") != "token-1",
			"unexpected query: %s", r.URL.RawQuery)

		_, _ = w.Write([]byte("file contents"))
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Setenv("LIGHTNING_AUTH_TOKEN", "token-1")

	targetPath := filepath.Join(t.TempDir(), "downloaded.txt")
	s := mustStudio(t, "studio-1", "project-1", lit.StudioOptions{Cloud: "cloud-1"})
	require.NoErrorf(t, s.DownloadFile("remote.txt", targetPath),
		"studio.DownloadFile returned error")

	got, err := os.ReadFile(targetPath)
	require.NoErrorf(t, err,
		"read downloaded file")
	assert.Falsef(t, string(got) != "file contents",
		"downloaded file = %q, want file contents", string(got))

}

func TestStudioDownloadFolderUsesRecursiveTree(t *testing.T) {
	var seen []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1/artifacts/cloudspaces/studio-1/trees/remote":
			query := r.URL.Query()
			if query.Get("recursive") != "true" || query.Get("token") != "token-1" {
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
		case "GET /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/a.txt":
			if token := r.URL.Query().Get("token"); token != "token-1" {
				assert.Fail(t, fmt.Sprintf("download token = %q, want token-1", token))
			}
			_, _ = w.Write([]byte("a"))
		case "GET /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/nested/b.txt":
			if token := r.URL.Query().Get("token"); token != "token-1" {
				assert.Fail(t, fmt.Sprintf("download token = %q, want token-1", token))
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
	s := mustStudio(t, "studio-1", "project-1")
	require.NoErrorf(t, s.DownloadFolder("remote", targetDir),
		"studio.DownloadFolder returned error")

	gotA, err := os.ReadFile(filepath.Join(targetDir, "a.txt"))
	require.NoErrorf(t, err,
		"read a.txt")

	gotB, err := os.ReadFile(filepath.Join(targetDir, "nested", "b.txt"))
	require.NoErrorf(t, err,
		"read nested/b.txt")
	assert.Falsef(t, string(gotA) != "a" || string(gotB) != "b",
		"downloaded files = (%q, %q), want (a, b)", string(gotA), string(gotB))

	want := []string{
		"GET /v1/projects/project-1/artifacts/cloudspaces/studio-1/trees/remote?recursive=true&token=token-1",
		"GET /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/a.txt?token=token-1",
		"GET /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/nested/b.txt?token=token-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioUploadFileUsesArtifactBlobRouteAndCompletion(t *testing.T) {
	var seen []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		switch r.Method + " " + r.URL.Path {
		case "PUT /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote.txt":
			if token := r.URL.Query().Get("token"); token != "token-1" {
				assert.Fail(t, fmt.Sprintf("token = %q, want token-1", token))
			}
			body, err := io.ReadAll(r.Body)
			if err != nil {
				assert.Fail(t, fmt.Sprintf("read upload body: %v", err))
			}
			if string(body) != "upload contents" {
				assert.Fail(t, fmt.Sprintf("upload body = %q, want upload contents", string(body)))
			}
		case "POST /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote.txt/complete":
			if token := r.URL.Query().Get("token"); token != "token-1" {
				assert.Fail(t, fmt.Sprintf("complete token = %q, want token-1", token))
			}
			w.WriteHeader(http.StatusNoContent)
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Setenv("LIGHTNING_AUTH_TOKEN", "token-1")

	sourcePath := filepath.Join(t.TempDir(), "source.txt")
	require.NoErrorf(t, os.WriteFile(sourcePath, []byte("upload contents"), 0o600),
		"write source file")

	s := mustStudio(t, "studio-1", "project-1")
	require.NoErrorf(t, s.UploadFile(sourcePath, "remote.txt"),
		"studio.UploadFile returned error")

	want := []string{
		"PUT /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote.txt?token=token-1",
		"POST /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote.txt/complete?token=token-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioUploadFolderPreservesRelativePaths(t *testing.T) {
	var seen []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		assert.Falsef(t, r.Method != http.MethodPut && r.Method != http.MethodPost,
			"unexpected method: %s", r.Method)

		switch r.URL.Path {
		case "/v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/a.txt",
			"/v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/a.txt/complete",
			"/v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/nested/b.txt",
			"/v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/nested/b.txt/complete":
			if token := r.URL.Query().Get("token"); token != "token-1" {
				assert.Fail(t, fmt.Sprintf("token = %q, want token-1", token))
			}
			if r.Method == http.MethodPost {
				w.WriteHeader(http.StatusNoContent)
			}
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

	s := mustStudio(t, "studio-1", "project-1")
	require.NoErrorf(t, s.UploadFolder(sourceDir, "remote"),
		"studio.UploadFolder returned error")

	want := []string{
		"PUT /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/a.txt?token=token-1",
		"POST /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/a.txt/complete?token=token-1",
		"PUT /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/nested/b.txt?token=token-1",
		"POST /v1/projects/project-1/artifacts/cloudspaces/studio-1/blobs/remote/nested/b.txt/complete?token=token-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioRunWithExitCodeSubmitsAndPollsCommand(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects/project-1/cloudspaces/studio-1/execute":
			var body struct {
				Command  string `json:"command"`
				Detached bool   `json:"detached"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode execute body: %v", err))
			}
			if body.Command != "echo hello; pwd" || !body.Detached {
				assert.Fail(t, fmt.Sprintf("unexpected execute body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"sessionName": "session-1",
			})
		case "GET /v1/projects/project-1/cloudspaces/studio-1/execute/session-1":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"output":   "hello\n",
				"exitCode": 0,
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s := mustStudio(t, "studio-1", "project-1", lit.StudioOptions{Status: "Running"})
	output, exitCode, err := s.RunWithExitCode("echo hello", "pwd")
	require.NoErrorf(t, err,
		"studio.RunWithExitCode returned error")
	assert.Falsef(t, output != "hello" || exitCode != 0,
		"RunWithExitCode = (%q, %d), want (hello, 0)", output, exitCode)

	want := []string{
		"POST /v1/projects/project-1/cloudspaces/studio-1/execute",
		"GET /v1/projects/project-1/cloudspaces/studio-1/execute/session-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioRunReturnsCommandOutputAsErrorOnNonZeroExit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects/project-1/cloudspaces/studio-1/execute":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"sessionName": "session-1",
			})
		case "GET /v1/projects/project-1/cloudspaces/studio-1/execute/session-1":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"output":   "boom\n",
				"exitCode": 42,
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s := mustStudio(t, "studio-1", "project-1", lit.StudioOptions{Status: "Running"})
	output, err := s.Run("false")
	require.Errorf(t, err,
		"studio.Run returned nil error, want command output error")
	assert.Falsef(t, output != "",
		"studio.Run output = %q, want empty output on error", output)
	assert.Falsef(t, err.Error() != "boom",
		"studio.Run error = %q, want boom", err.Error())

}

func TestStudioRunAndDetachPollsUntilCommandCompletes(t *testing.T) {
	polls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects/project-1/cloudspaces/studio-1/execute":
			var body struct {
				Command  string `json:"command"`
				Detached bool   `json:"detached"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode execute body: %v", err))
			}
			if body.Command != "sleep 1; echo done" || !body.Detached {
				assert.Fail(t, fmt.Sprintf("unexpected execute body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"sessionName": "session-1",
			})
		case "GET /v1/projects/project-1/cloudspaces/studio-1/execute/session-1":
			polls++
			if polls == 1 {
				_ = json.NewEncoder(w).Encode(map[string]any{
					"exitCode": -1,
				})
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"output":   "done\n",
				"exitCode": 0,
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s := mustStudio(t, "studio-1", "project-1", lit.StudioOptions{Status: "Running"})
	output, exitCode, err := s.RunAndDetach(
		[]string{"sleep 1", "echo done"},
		lit.RunAndDetachOptions{Timeout: time.Second, CheckInterval: time.Millisecond},
	)
	require.NoErrorf(t, err,
		"studio.RunAndDetach returned error")
	assert.Falsef(t, output != "done\n" || exitCode != 0,
		"RunAndDetach = (%q, %d), want (done newline, 0)", output, exitCode)
	assert.Falsef(t, polls != 2,
		"polls = %d, want 2", polls)

}

func TestStudioMapsAndSetsEnvironmentVariables(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/users/alice/projects/default/cloudspaces/dev/getbyname":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"cloudspace": map[string]any{
					"id":        "studio-1",
					"name":      "dev",
					"projectId": "project-1",
					"env": []map[string]any{
						{"name": "KEEP", "value": "yes"},
						{"name": "OLD", "value": "value"},
					},
				},
				"project": map[string]any{
					"id":   "project-1",
					"name": "default",
				},
			})
		case "PUT /v1/projects/project-1/cloudspaces/studio-1":
			var body struct {
				Env []struct {
					Name  string `json:"name"`
					Value string `json:"value"`
				} `json:"env"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode set env body: %v", err))
			}
			got := map[string]string{}
			for _, env := range body.Env {
				got[env.Name] = env.Value
			}
			want := map[string]string{"NEW": "set"}
			if len(got) != len(want) || got["NEW"] != want["NEW"] {
				assert.Fail(t, fmt.Sprintf("env body = %+v, want %+v", got, want))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "studio-1",
				"name":      "dev",
				"projectId": "project-1",
				"env": []map[string]any{
					{"name": "NEW", "value": "set"},
				},
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s, err := lit.GetStudio("dev", lit.StudioOptions{Teamspace: mustTeamspace(t, "project-1", "default", "alice")})
	require.NoErrorf(t, err,
		"studio.New returned error")
	assert.Falsef(t, s.Env()["KEEP"] != "yes" || s.Env()["OLD"] != "value",
		"unexpected mapped env: %+v", s.Env())
	require.NoErrorf(t, s.SetEnv(map[string]string{"NEW": "set"}, false),
		"studio.SetEnv returned error")
	assert.Falsef(t, len(s.Env()) != 1 || s.Env()["NEW"] != "set",
		"unexpected env after replace: %+v", s.Env())

	want := []string{
		"GET /v1/users/alice/projects/default/cloudspaces/dev/getbyname?projectId=project-1",
		"PUT /v1/projects/project-1/cloudspaces/studio-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioSetEnvMergesByDefault(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodPut || r.URL.Path != "/v1/projects/project-1/cloudspaces/studio-1",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		var body struct {
			Env []struct {
				Name  string `json:"name"`
				Value string `json:"value"`
			} `json:"env"`
		}
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode set env body")

		got := map[string]string{}
		for _, env := range body.Env {
			got[env.Name] = env.Value
		}
		assert.Falsef(t, len(got) != 2 || got["KEEP"] != "yes" || got["NEW"] != "set",
			"env body = %+v, want merged KEEP and NEW", got)

		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":        "studio-1",
			"name":      "dev",
			"projectId": "project-1",
			"env": []map[string]any{
				{"name": "KEEP", "value": "yes"},
				{"name": "NEW", "value": "set"},
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s := func() *lit.Studio {
		result, err := lit.GetStudio("dev", lit.StudioOptions{ID: "studio-1", Teamspace: mustTeamspace(t, "project-1", ""), Env: map[string]string{"KEEP": "yes"}})
		require.NoErrorf(t, err,
			"studio.New returned error")

		return result
	}()
	require.NoErrorf(t, s.SetEnv(map[string]string{"NEW": "set"}, true),
		"studio.SetEnv returned error")
	assert.Falsef(t, len(s.Env()) != 2 || s.Env()["KEEP"] != "yes" || s.Env()["NEW"] != "set",
		"unexpected env after merge: %+v", s.Env())

}

func TestStudioListsPluginsThroughGeneratedRoutes(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/cloudspaces/plugins":
			if r.URL.Query().Get("id") != "studio-1" || r.URL.Query().Get("projectId") != "project-1" {
				assert.Fail(t, fmt.Sprintf("unexpected available plugins query: %s", r.URL.RawQuery))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"plugins": map[string]string{
					"jobs":        "Jobs",
					"custom-port": "Custom Port",
				},
			})
		case "GET /v1/projects/project-1/cloudspaces/studio-1/plugins":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"plugins": map[string]string{
					"jobs": "Jobs",
				},
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s := mustStudio(t, "studio-1", "project-1")
	available, err := s.AvailablePlugins()
	require.NoErrorf(t, err,
		"studio.AvailablePlugins returned error")
	assert.Falsef(t, available["jobs"] != "Jobs" || available["custom-port"] != "Custom Port",
		"available plugins = %v", available)

	installed, err := s.InstalledPlugins()
	require.NoErrorf(t, err,
		"studio.InstalledPlugins returned error")
	assert.Falsef(t, installed["jobs"] != "Jobs" || len(installed) != 1,
		"installed plugins = %v", installed)

	want := []string{
		"GET /v1/cloudspaces/plugins?id=studio-1&projectId=project-1",
		"GET /v1/projects/project-1/cloudspaces/studio-1/plugins",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioInstallsRunsAndUninstallsPluginsThroughGeneratedRoutes(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects/project-1/cloudspaces/studio-1/plugins/custom-port":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"state":          "installation_success",
				"error":          "",
				"additionalInfo": "\ninstalled\n",
			})
		case "POST /v1/projects/project-1/cloudspaces/studio-1/plugins/custom-port/execute":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"state":          "execution_success",
				"error":          "",
				"additionalInfo": `{"port": 8080}`,
			})
		case "DELETE /v1/projects/project-1/cloudspaces/studio-1/plugins/custom-port":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"state": "uninstallation_success",
				"error": "",
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s := mustStudio(t, "studio-1", "project-1")
	require.NoErrorf(t, s.InstallPlugin("custom-port"),
		"studio.InstallPlugin returned error")

	output, err := s.RunPlugin("custom-port")
	require.NoErrorf(t, err,
		"studio.RunPlugin returned error")

	wantOutput := "Plugin custom-port is interactive. Have a look at https://8080-studio-1.cloudspaces.litng.ai"
	assert.Falsef(t, output != wantOutput,
		"run plugin output = %q, want %q", output, wantOutput)
	require.NoErrorf(t, s.UninstallPlugin("custom-port"),
		"studio.UninstallPlugin returned error")

	want := []string{
		"POST /v1/projects/project-1/cloudspaces/studio-1/plugins/custom-port",
		"POST /v1/projects/project-1/cloudspaces/studio-1/plugins/custom-port/execute",
		"DELETE /v1/projects/project-1/cloudspaces/studio-1/plugins/custom-port",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioMapsAndUpdatesAutoSleepConfig(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/users/alice/projects/default/cloudspaces/dev/getbyname":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"cloudspace": map[string]any{
					"id":        "studio-1",
					"name":      "dev",
					"projectId": "project-1",
					"codeConfig": map[string]any{
						"disableAutoShutdown": true,
						"idleShutdownSeconds": 600,
					},
				},
				"project": map[string]any{
					"id":   "project-1",
					"name": "default",
				},
			})
		case "PUT /v1/projects/project-1/cloudspaces/studio-1/sleepconfig":
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode sleep config body: %v", err))
			}
			switch len(seen) {
			case 2:
				value, ok := body["disableAutoShutdown"]
				if !ok || value != false {
					assert.Fail(t, fmt.Sprintf("disableAutoShutdown body = %#v, want explicit false", body))
				}
				_ = json.NewEncoder(w).Encode(map[string]any{
					"disableAutoShutdown": false,
					"idleShutdownSeconds": 600,
				})
			case 3:
				if got := body["idleShutdownSeconds"]; got != float64(1200) {
					assert.Fail(t, fmt.Sprintf("idleShutdownSeconds body = %#v, want 1200", body))
				}
				_ = json.NewEncoder(w).Encode(map[string]any{
					"disableAutoShutdown": false,
					"idleShutdownSeconds": 1200,
				})
			case 4:
				value, ok := body["disableAutoShutdown"]
				if !ok || value != true {
					assert.Fail(t, fmt.Sprintf("disableAutoShutdown body = %#v, want explicit true", body))
				}
				_ = json.NewEncoder(w).Encode(map[string]any{
					"disableAutoShutdown": true,
					"idleShutdownSeconds": 1200,
				})
			case 5:
				if got := body["idleShutdownSeconds"]; got != float64(1800) {
					assert.Fail(t, fmt.Sprintf("idleShutdownSeconds body = %#v, want 1800", body))
				}
				_ = json.NewEncoder(w).Encode(map[string]any{
					"disableAutoShutdown": true,
					"idleShutdownSeconds": 1800,
				})
			default:
				assert.Fail(t, fmt.Sprintf("unexpected request count %d", len(seen)))
			}
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s, err := lit.GetStudio("dev", lit.StudioOptions{Teamspace: mustTeamspace(t, "project-1", "default", "alice")})
	require.NoErrorf(t, err,
		"studio.New returned error")
	assert.Falsef(t, s.AutoSleep() || s.AutoSleepTime() != 600,
		"unexpected initial sleep config: autoSleep=%v autoSleepTime=%d", s.AutoSleep(), s.AutoSleepTime())
	require.NoErrorf(t, s.SetAutoSleep(true),
		"studio.SetAutoSleep returned error")
	assert.Falsef(t, !s.AutoSleep() || s.AutoSleepTime() != 600,
		"unexpected sleep config after enabling: autoSleep=%v autoSleepTime=%d", s.AutoSleep(), s.AutoSleepTime())
	require.NoErrorf(t, s.SetAutoSleepTime(1200),
		"studio.SetAutoSleepTime returned error")
	assert.Falsef(t, !s.AutoSleep() || s.AutoSleepTime() != 1200,
		"unexpected sleep config after idle timeout: autoSleep=%v autoSleepTime=%d", s.AutoSleep(), s.AutoSleepTime())
	require.NoErrorf(t, s.SetAutoShutdown(false),
		"studio.SetAutoShutdown returned error")
	assert.Falsef(t, s.AutoSleep() || s.AutoSleepTime() != 1200,
		"unexpected sleep config after disabling via auto shutdown: autoSleep=%v autoSleepTime=%d", s.AutoSleep(), s.AutoSleepTime())
	require.NoErrorf(t, s.SetAutoShutdownTime(1800),
		"studio.SetAutoShutdownTime returned error")
	assert.Falsef(t, s.AutoSleep() || s.AutoSleepTime() != 1800,
		"unexpected sleep config after auto shutdown timeout: autoSleep=%v autoSleepTime=%d", s.AutoSleep(), s.AutoSleepTime())

}

func TestStudioSwitchMachineUsesCodeConfigRoute(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodPut || r.URL.Path != "/v1/projects/project-1/cloudspaces/studio-1/codeconfig",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		var body struct {
			ComputeConfig struct {
				Name            string `json:"name"`
				Spot            bool   `json:"spot"`
				ClusterOverride string `json:"clusterOverride"`
			} `json:"computeConfig"`
		}
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode switch machine body")
		assert.Falsef(t, body.ComputeConfig.Name != "gpu-fast" || !body.ComputeConfig.Spot || body.ComputeConfig.ClusterOverride != "cloud-2",
			"unexpected compute config body: %+v", body.ComputeConfig)

		_ = json.NewEncoder(w).Encode(map[string]any{
			"computeConfig": map[string]any{
				"name":            "gpu-fast",
				"spot":            true,
				"clusterOverride": "cloud-2",
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	s := mustStudio(t, "studio-1", "project-1", lit.StudioOptions{Machine: "cpu", Cloud: "cloud-1"})
	interruptible := true
	require.NoErrorf(t, s.SwitchMachine("gpu-fast", lit.SwitchMachineOptions{Cloud: "cloud-2", Interruptible: &interruptible}),
		"studio.SwitchMachine returned error")
	assert.Falsef(t, s.Machine() != "gpu-fast" || !s.Interruptible() || s.Cloud() != "cloud-2",
		"unexpected switched studio: %+v", s)

	want := []string{"PUT /v1/projects/project-1/cloudspaces/studio-1/codeconfig"}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestStudioDuplicateUsesForkRoute(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodPut || r.URL.Path != "/v1/projects/source-project/cloudspaces/source-studio/fork",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		var body struct {
			NewName         string `json:"newName"`
			TargetProjectID string `json:"targetProjectId"`
		}
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode duplicate body")
		assert.Falsef(t, body.NewName != "copy-dev" || body.TargetProjectID != "target-project",
			"unexpected duplicate body: %+v", body)

		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":        "copy-studio",
			"name":      "copy-dev",
			"projectId": "target-project",
			"clusterId": "cloud-2",
			"state":     "CLOUD_SPACE_STATE_READY",
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	sourceTeamspace := mustTeamspace(t, "source-project", "source", "alice")
	s, err := lit.GetStudio("dev", lit.StudioOptions{ID: "source-studio", Teamspace: sourceTeamspace, Cloud: "cloud-1"})
	require.NoErrorf(t, err,
		"studio.New returned error")

	duplicate, err := s.Duplicate(
		lit.DuplicateStudioOptions{Name: "copy-dev", Teamspace: mustTeamspace(t, "target-project", "target", "alice")},
	)
	require.NoErrorf(t, err,
		"studio.Duplicate returned error")
	assert.Falsef(t, duplicate.ID() != "copy-studio" || duplicate.Name() != "copy-dev" || duplicate.TeamspaceID() != "target-project",
		"unexpected duplicate studio: %+v", duplicate)
	assert.Falsef(t, duplicate.Teamspace() != "target" || duplicate.OwnerName() != "alice" || duplicate.Cloud() != "cloud-2",
		"unexpected duplicate context: %+v", duplicate)

	want := []string{"PUT /v1/projects/source-project/cloudspaces/source-studio/fork"}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}
