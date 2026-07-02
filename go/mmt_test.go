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
)

func TestMMTGetWithIDUsesSimpleStruct(t *testing.T) {
	m, err := lit.GetMMT("dist-train", lit.MMTOptions{ID: "mmt-1", Teamspace: mustTeamspace(t, "project-1", "")})
	require.NoErrorf(t, err,
		"GetMMT returned error")
	assert.Falsef(t, m.ID() != "mmt-1" || m.Name() != "dist-train" || m.TeamspaceID() != "project-1",
		"unexpected mmt: %s %s %s", m.ID(), m.Name(), m.TeamspaceID())

}

func TestMMTExposesWebLinks(t *testing.T) {
	m, err := lit.GetMMT("dist-train", lit.MMTOptions{ID: "mmt-1", Teamspace: mustTeamspace(t, "project-1", "default", "alice")})
	require.NoErrorf(t, err,
		"GetMMT returned error")

	if got, want := m.Link(), "https://lightning.ai/alice/default/jobs/dist-train?app_id=mmt"; got != want {
		assert.Fail(t, fmt.Sprintf("mmt link = %q, want %q", got, want))
	}
}

func TestMMTExposesPublicDictionaryAndJSON(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/projects/project-1/jobs",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())
		assert.Falsef(t, r.URL.Query().Get("multiMachineJobId") != "mmt-1",
			"multiMachineJobId = %q, want mmt-1", r.URL.Query().Get("multiMachineJobId"))

		_ = json.NewEncoder(w).Encode(map[string]any{
			"jobs": []map[string]any{
				{
					"id":                "job-rank-0",
					"name":              "dist-train-0",
					"projectId":         "project-1",
					"state":             "running",
					"multiMachineJobId": "mmt-1",
					"spec": map[string]any{
						"command":      "torchrun train.py",
						"image":        "pytorch/pytorch:latest",
						"instanceName": "gpu",
					},
				},
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "default", "alice")
	m, err := lit.GetMMT("dist-train", lit.MMTOptions{ID: "mmt-1", Teamspace: ts, Studio: mustStudio(t, "studio-1", "project-1", lit.StudioOptions{Teamspace: ts}), Command: "torchrun train.py", Status: "completed", Machine: "gpu", TotalCost: 4.5})
	require.NoErrorf(t, err,
		"GetMMT returned error")

	dict, err := m.Dict()
	require.NoErrorf(t, err,
		"mmt.Dict returned error")
	assert.Falsef(t, dict.Name != "dist-train" || dict.Teamspace != "alice/default" || dict.Command != "torchrun train.py" || dict.Status != "completed" || dict.Machine != "gpu" || dict.TotalCost != 4.5,
		"unexpected mmt dict: %+v", dict)
	require.NotNil(t, dict.Studio)
	assert.Equal(t, "studio-1", *dict.Studio)
	assert.Nil(t, dict.Image)
	assert.Falsef(t, len(dict.Machines) != 1 || dict.Machines[0].Name != "dist-train-0" || dict.Machines[0].Status != "running" || dict.Machines[0].Machine != "gpu",
		"unexpected mmt machines: %+v", dict.Machines)

	body, err := m.JSON()
	require.NoErrorf(t, err,
		"mmt.JSON returned error")

	var decoded map[string]any
	require.NoErrorf(t, json.Unmarshal([]byte(body), &decoded),
		"mmt.JSON returned invalid JSON %q", body)

	machines, ok := decoded["machines"].([]any)
	assert.Falsef(t, !ok || len(machines) != 1,
		"decoded machines = %#v, want one machine", decoded["machines"])
	assert.Falsef(t, decoded["name"] != "dist-train" || decoded["teamspace"] != "alice/default" || decoded["studio"] != "studio-1" || decoded["image"] != nil || decoded["command"] != "torchrun train.py" || decoded["status"] != "completed" || decoded["machine"] != "gpu" || decoded["total_cost"] != 4.5,
		"unexpected mmt JSON: %s", body)
	assert.Truef(t, strings.Contains(body, "\n    \"machines\""),
		"mmt.JSON is not indented: %q", body)

	want := []string{
		"GET /v1/projects/project-1/jobs?multiMachineJobId=mmt-1",
		"GET /v1/projects/project-1/jobs?multiMachineJobId=mmt-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestMMTExposesFilesystemPaths(t *testing.T) {
	studioMMT, err := lit.GetMMT("dist-train", lit.MMTOptions{ID: "mmt-studio"})
	require.NoErrorf(t, err,
		"GetMMT returned error")

	if got := studioMMT.ArtifactPath(); got != "" {
		assert.Fail(t, fmt.Sprintf("mmt artifact path = %q, want empty", got))
	}
	if got := studioMMT.SnapshotPath(); got != "" {
		assert.Fail(t, fmt.Sprintf("mmt snapshot path = %q, want empty", got))
	}
	if got := studioMMT.SharePath(); got != "" {
		assert.Fail(t, fmt.Sprintf("share path = %q, want empty", got))
	}

	imageMMT, err := lit.GetMMT("image-dist-train", lit.MMTOptions{ID: "mmt-image", Image: "pytorch/pytorch:latest"})
	require.NoErrorf(t, err,
		"GetMMT returned error")

	if got := imageMMT.ArtifactPath(); got != "" {
		assert.Fail(t, fmt.Sprintf("image mmt artifact path = %q, want empty", got))
	}
	if got := imageMMT.SnapshotPath(); got != "" {
		assert.Fail(t, fmt.Sprintf("image mmt snapshot path = %q, want empty", got))
	}
}

func TestMMTUsesDefaultClientAndV2GeneratedRoutes(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1/multi-machine-jobs/dist-train/getbyname":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "mmt-1",
				"name":      "dist-train",
				"projectId": "project-1",
				"machines":  4,
				"state":     "running",
			})
		case "POST /v1/projects/project-1/multi-machine-jobs":
			var body struct {
				Name     string `json:"name"`
				Machines int64  `json:"machines"`
				Spec     struct {
					Command      string `json:"command"`
					Entrypoint   string `json:"entrypoint"`
					InstanceName string `json:"instanceName"`
					Image        string `json:"image"`
				} `json:"spec"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode mmt body: %v", err))
			}
			if body.Name != "dist-train-2" || body.Machines != 8 || body.Spec.Command != "torchrun train.py" || body.Spec.Entrypoint != "sh -c" || body.Spec.InstanceName != "gpu" || body.Spec.Image != "pytorch/pytorch:latest" {
				assert.Fail(t, fmt.Sprintf("unexpected mmt body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "mmt-2",
				"name":      "dist-train-2",
				"projectId": "project-1",
				"machines":  8,
				"state":     "pending",
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "")
	existing, err := lit.GetMMT("dist-train", lit.MMTOptions{Teamspace: ts})
	require.NoErrorf(t, err,
		"GetMMT returned error")
	assert.Falsef(t, existing.ID() != "mmt-1" || existing.Status() != "running" || existing.NumMachines() != 4,
		"unexpected fetched mmt: %s %s %d", existing.ID(), existing.Status(), existing.NumMachines())

	created, err := lit.RunMMT("dist-train-2", 8, "gpu", "torchrun train.py", lit.MMTOptions{Teamspace: ts, Image: "pytorch/pytorch:latest"})
	require.NoErrorf(t, err,
		"RunMMT returned error")
	assert.Falsef(t, created.ID() != "mmt-2" || created.Status() != "pending" || created.NumMachines() != 8,
		"unexpected created mmt: %s %s %d", created.ID(), created.Status(), created.NumMachines())

	want := []string{
		"GET /v1/projects/project-1/multi-machine-jobs/dist-train/getbyname",
		"POST /v1/projects/project-1/multi-machine-jobs",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestMMTRunValidatesComputeEnvironment(t *testing.T) {
	studio := mustStudio(t, "studio-1", "project-1")
	cases := []struct {
		name    string
		command string
		opts    lit.MMTOptions
		want    string
	}{
		{
			name:    "missing image or studio",
			command: "torchrun train.py",
			want:    "either image or studio must be provided",
		},
		{
			name:    "image and studio",
			command: "torchrun train.py",
			opts:    lit.MMTOptions{Image: "pytorch/pytorch:latest", Studio: studio},
			want:    "image and studio are mutually exclusive",
		},
		{
			name:    "studio without command",
			command: "",
			opts:    lit.MMTOptions{Studio: studio},
			want:    "command is required when using a studio",
		},
		{
			name:    "artifacts with studio",
			command: "torchrun train.py",
			opts:    lit.MMTOptions{Studio: studio, ArtifactsSource: "/outputs", ArtifactsDestination: "efs:data:outputs"},
			want:    "artifacts are only supported when using a custom image",
		},
		{
			name:    "missing artifact remote path",
			command: "torchrun train.py",
			opts:    lit.MMTOptions{Image: "ubuntu:22.04", ArtifactsSource: "/outputs"},
			want:    "artifacts require both local and remote paths",
		},
		{
			name:    "invalid artifact remote path",
			command: "torchrun train.py",
			opts:    lit.MMTOptions{Image: "ubuntu:22.04", ArtifactsSource: "/outputs", ArtifactsDestination: "data"},
			want:    "artifact remote path must be",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := lit.RunMMT("dist-train", 2, "gpu", tc.command, tc.opts)
			assert.Falsef(t, err == nil || !strings.Contains(err.Error(), tc.want),
				"RunMMT error = %v, want containing %q", err, tc.want)

		})
	}
}

func TestMMTGetUsesExplicitTeamspace(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1/multi-machine-jobs/dist-train/getbyname":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "mmt-1",
				"name":      "dist-train",
				"projectId": "project-1",
				"machines":  4,
				"state":     "running",
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	existing, err := lit.GetMMT("dist-train", lit.MMTOptions{Teamspace: mustTeamspace(t, "project-1", "default", "alice")})
	require.NoErrorf(t, err,
		"GetMMT returned error")
	assert.Falsef(t, existing.ID() != "mmt-1" || existing.TeamspaceID() != "project-1" || existing.Teamspace() != "default" || existing.OwnerName() != "alice",
		"unexpected fetched mmt: %+v", existing)

	want := []string{
		"GET /v1/projects/project-1/multi-machine-jobs/dist-train/getbyname",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestMMTGetMapsTopLevelStudioID(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/projects/project-1/multi-machine-jobs/dist-train/getbyname",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":           "mmt-1",
			"name":         "dist-train",
			"projectId":    "project-1",
			"cloudspaceId": "studio-1",
			"machines":     4,
			"state":        "running",
			"spec": map[string]any{
				"instanceName": "gpu",
				"command":      "torchrun train.py",
				"image":        "registry.example/train:latest",
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	existing, err := lit.GetMMT("dist-train", lit.MMTOptions{Teamspace: mustTeamspace(t, "project-1", "")})
	require.NoErrorf(t, err,
		"GetMMT returned error")
	assert.Falsef(t, existing.StudioID() != "studio-1",
		"StudioID = %q, want studio-1", existing.StudioID())

}

func TestMMTRunMapsAdvancedV2Options(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodPost || r.URL.Path != "/v1/projects/project-1/multi-machine-jobs",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		var body struct {
			Name     string `json:"name"`
			Machines int64  `json:"machines"`
			Spec     struct {
				Entrypoint                  string `json:"entrypoint"`
				ImageClusterCredentials     bool   `json:"imageClusterCredentials"`
				ImageSecretRef              string `json:"imageSecretRef"`
				RequestedRunDurationSeconds string `json:"requestedRunDurationSeconds"`
				PathMappings                []struct {
					ContainerPath  string `json:"containerPath"`
					ConnectionName string `json:"connectionName"`
					ConnectionPath string `json:"connectionPath"`
				} `json:"pathMappings"`
			} `json:"spec"`
		}
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode mmt body")
		assert.Falsef(t, body.Name != "dist-train-advanced" || body.Machines != 4,
			"unexpected mmt header: %+v", body)
		assert.Falsef(t, body.Spec.Entrypoint != "python",
			"entrypoint = %q, want python", body.Spec.Entrypoint)
		assert.True(t, body.Spec.ImageClusterCredentials,
			"imageClusterCredentials = false, want true")
		assert.Falsef(t, body.Spec.ImageSecretRef != "docker-secret",
			"imageSecretRef = %q, want docker-secret", body.Spec.ImageSecretRef)
		assert.Falsef(t, body.Spec.RequestedRunDurationSeconds != "7200",
			"requestedRunDurationSeconds = %q, want 7200", body.Spec.RequestedRunDurationSeconds)
		assert.Falsef(t, len(body.Spec.PathMappings) != 2,
			"pathMappings length = %d, want 2", len(body.Spec.PathMappings))

		mapping := body.Spec.PathMappings[0]
		assert.Falsef(t, mapping.ContainerPath != "/data" || mapping.ConnectionName != "dataset" || mapping.ConnectionPath != "train",
			"unexpected path mapping: %+v", mapping)

		artifacts := body.Spec.PathMappings[1]
		assert.Falsef(t, artifacts.ContainerPath != "/outputs" || artifacts.ConnectionName != "data" || artifacts.ConnectionPath != "outputs/run-1",
			"unexpected artifact path mapping: %+v", artifacts)

		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":        "mmt-advanced",
			"name":      "dist-train-advanced",
			"projectId": "project-1",
			"machines":  4,
			"state":     "pending",
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	created, err := lit.RunMMT(
		"dist-train-advanced",
		4,
		"gpu",
		"train.py",
		lit.MMTOptions{
			Teamspace:            mustTeamspace(t, "project-1", ""),
			Image:                "registry.example/train:latest",
			ImageCredentials:     "docker-secret",
			CloudAccountAuth:     true,
			Entrypoint:           "python",
			MaxRuntime:           7200,
			ArtifactsSource:      "/outputs",
			ArtifactsDestination: "efs:data:outputs/run-1",
			PathMappings: []lit.MMTPathMapping{{
				ContainerPath:  "/data",
				ConnectionName: "dataset",
				ConnectionPath: "train",
			}},
		},
	)
	require.NoErrorf(t, err,
		"RunMMT returned error")
	assert.Falsef(t, created.ID() != "mmt-advanced" || created.Status() != "pending" || created.NumMachines() != 4,
		"unexpected created mmt: %s %s %d", created.ID(), created.Status(), created.NumMachines())

}

func TestMMTRunRejectsSingleMachine(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	_, err := lit.RunMMT("dist-train", 1, "gpu", "torchrun train.py", lit.MMTOptions{Teamspace: mustTeamspace(t, "project-1", "")})
	require.Error(t, err,
		"RunMMT returned nil error")
	assert.Truef(t, strings.Contains(err.Error(), "less than 2"),
		"RunMMT error = %q, want less than 2 validation", err)

}

func TestMMTRunUsesExplicitTeamspace(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects/project-1/multi-machine-jobs":
			var body struct {
				ClusterID string `json:"clusterId"`
				Name      string `json:"name"`
				Machines  int64  `json:"machines"`
				Spec      struct {
					Command      string `json:"command"`
					ClusterID    string `json:"clusterId"`
					InstanceName string `json:"instanceName"`
				} `json:"spec"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode mmt body: %v", err))
			}
			if body.ClusterID != "aws-us-east" || body.Name != "dist-train-resolved" || body.Machines != 4 || body.Spec.Command != "torchrun train.py" || body.Spec.ClusterID != "aws-us-east" || body.Spec.InstanceName != "gpu" {
				assert.Fail(t, fmt.Sprintf("unexpected mmt body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "mmt-resolved",
				"name":      "dist-train-resolved",
				"projectId": "project-1",
				"machines":  4,
				"state":     "pending",
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	created, err := lit.RunMMT(
		"dist-train-resolved",
		4,
		"gpu",
		"torchrun train.py",
		lit.MMTOptions{Teamspace: mustTeamspace(t, "project-1", "default", "alice"), Cloud: "aws-us-east", Image: "pytorch/pytorch:latest"},
	)
	require.NoErrorf(t, err,
		"RunMMT returned error")
	assert.Falsef(t, created.ID() != "mmt-resolved" || created.TeamspaceID() != "project-1" || created.Teamspace() != "default" || created.OwnerName() != "alice",
		"unexpected created mmt: %+v", created)

	want := []string{
		"POST /v1/projects/project-1/multi-machine-jobs",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestMMTRunRejectsMissingTeamspace(t *testing.T) {
	_, err := lit.RunMMT("dist-train", 4, "gpu", "torchrun train.py", lit.MMTOptions{Image: "pytorch/pytorch:latest"})
	assert.Falsef(t, err == nil || !strings.Contains(err.Error(), "requires teamspace or studio"),
		"RunMMT error = %v, want teamspace validation", err)

}
