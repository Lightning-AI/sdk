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

func TestJobGetWithIDUsesSimpleStruct(t *testing.T) {
	j, err := lit.GetJob("train", lit.JobOptions{ID: "job-1", Teamspace: mustTeamspace(t, "project-1", "")})
	require.NoErrorf(t, err,
		"GetJob returned error")
	assert.Falsef(t, j.ID() != "job-1" || j.Name() != "train" || j.TeamspaceID() != "project-1",
		"unexpected job: %s %s %s", j.ID(), j.Name(), j.TeamspaceID())

}

func TestJobExposesWebLinks(t *testing.T) {
	ts := mustTeamspace(t, "project-1", "default", "alice")

	j, err := lit.GetJob("train", lit.JobOptions{ID: "job-1", Teamspace: ts})
	require.NoErrorf(t, err,
		"GetJob returned error")

	if got, want := j.Link(), "https://lightning.ai/alice/default/jobs/train"; got != want {
		assert.Fail(t, fmt.Sprintf("job link = %q, want %q", got, want))
	}

	imageJob, err := lit.GetJob("image-train", lit.JobOptions{ID: "job-image", Teamspace: ts, Image: "pytorch/pytorch:latest"})
	require.NoErrorf(t, err,
		"GetJob returned error")

	if got, want := imageJob.Link(), "https://lightning.ai/alice/default/jobs/image-train?app_id=jobs"; got != want {
		assert.Fail(t, fmt.Sprintf("image job link = %q, want %q", got, want))
	}

	mmtMachine, err := lit.GetJob("dist-train-0", lit.JobOptions{ID: "job-1", Teamspace: ts, MMT: mustMMT(t, "mmt-1", "dist-train", "project-1", lit.MMTOptions{Teamspace: ts}), Image: "pytorch/pytorch:latest"})
	require.NoErrorf(t, err,
		"GetJob returned error")

	if got, want := mmtMachine.Link(), "https://lightning.ai/alice/default/jobs/dist-train-0"; got != want {
		assert.Fail(t, fmt.Sprintf("mmt machine link = %q, want %q", got, want))
	}
}

func TestJobExposesPublicDictionaryAndJSON(t *testing.T) {
	ts := mustTeamspace(t, "project-1", "default", "alice")
	studio := mustStudio(t, "studio-1", "project-1", lit.StudioOptions{Teamspace: ts})
	j, err := lit.GetJob("train", lit.JobOptions{ID: "job-1", Teamspace: ts, Studio: studio, Command: "python train.py", Status: "completed", Machine: "gpu", TotalCost: 1.25})
	require.NoErrorf(t, err,
		"GetJob returned error")

	dict := j.Dict()
	assert.Falsef(t, dict.Name != "train" || dict.Teamspace != "alice/default" || dict.Command != "python train.py" || dict.Status != "completed" || dict.Machine != "gpu" || dict.TotalCost != 1.25,
		"unexpected job dict: %+v", dict)
	require.NotNil(t, dict.Studio)
	assert.Equal(t, "studio-1", *dict.Studio)
	assert.Nil(t, dict.Image)

	imageJob, err := lit.GetJob("image-train", lit.JobOptions{ID: "job-image", Teamspace: ts, Image: "ubuntu:22.04"})
	require.NoErrorf(t, err,
		"GetJob returned error")

	imageDict := imageJob.Dict()
	require.NotNil(t, imageDict.Image)
	assert.Equal(t, "ubuntu:22.04", *imageDict.Image)

	body, err := j.JSON()
	require.NoErrorf(t, err,
		"job.JSON returned error")

	var decoded map[string]any
	require.NoErrorf(t, json.Unmarshal([]byte(body), &decoded),
		"job.JSON returned invalid JSON %q", body)
	assert.Falsef(t, decoded["name"] != "train" || decoded["teamspace"] != "alice/default" || decoded["studio"] != "studio-1" || decoded["image"] != nil || decoded["command"] != "python train.py" || decoded["status"] != "completed" || decoded["machine"] != "gpu" || decoded["total_cost"] != 1.25,
		"unexpected job JSON: %s", body)
	assert.Truef(t, strings.Contains(body, "\n    \"name\""),
		"job.JSON is not indented: %q", body)

}

func TestJobExposesFilesystemPaths(t *testing.T) {
	studioJob, err := lit.GetJob("train", lit.JobOptions{ID: "job-studio"})
	require.NoErrorf(t, err,
		"GetJob returned error")

	if got, want := studioJob.ArtifactPath(), "/teamspace/jobs/train/artifacts"; got != want {
		assert.Fail(t, fmt.Sprintf("artifact path = %q, want %q", got, want))
	}
	if got, want := studioJob.SnapshotPath(), "/teamspace/jobs/train/snapshot"; got != want {
		assert.Fail(t, fmt.Sprintf("snapshot path = %q, want %q", got, want))
	}
	if got := studioJob.SharePath(); got != "" {
		assert.Fail(t, fmt.Sprintf("share path = %q, want empty", got))
	}

	imageJob, err := lit.GetJob("image-train", lit.JobOptions{ID: "job-image", Image: "ubuntu:22.04"})
	require.NoErrorf(t, err,
		"GetJob returned error")

	if got := imageJob.ArtifactPath(); got != "" {
		assert.Fail(t, fmt.Sprintf("image job artifact path = %q, want empty", got))
	}
	persistedImageJob, err := lit.GetJob("image-train", lit.JobOptions{ID: "job-image-persisted", Image: "ubuntu:22.04", ArtifactsDestination: "efs:data:outputs/run-1"})
	require.NoErrorf(t, err,
		"GetJob returned error")

	if got, want := persistedImageJob.ArtifactPath(), "/teamspace/efs_connections/data/outputs/run-1"; got != want {
		assert.Fail(t, fmt.Sprintf("persisted image job artifact path = %q, want %q", got, want))
	}
	if got := imageJob.SnapshotPath(); got != "" {
		assert.Fail(t, fmt.Sprintf("image job snapshot path = %q, want empty", got))
	}
}

func TestJobUsesDefaultClientAndV2GeneratedRoutes(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/-/-/jobs/train":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "job-1",
				"name":      "train",
				"projectId": "project-1",
				"state":     "running",
				"spec": map[string]any{
					"command":      "python train.py",
					"instanceName": "cpu",
					"image":        "ubuntu:22.04",
				},
			})
		case "POST /v1/projects/project-1/jobs":
			var body struct {
				Name string `json:"name"`
				Spec struct {
					Command      string `json:"command"`
					Entrypoint   string `json:"entrypoint"`
					InstanceName string `json:"instanceName"`
					Image        string `json:"image"`
				} `json:"spec"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode job body: %v", err))
			}
			if body.Name != "train-2" || body.Spec.Command != "python train.py" || body.Spec.Entrypoint != "sh -c" || body.Spec.InstanceName != "cpu" || body.Spec.Image != "ubuntu:22.04" {
				assert.Fail(t, fmt.Sprintf("unexpected job body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "job-2",
				"name":      "train-2",
				"projectId": "project-1",
				"state":     "pending",
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	ts := mustTeamspace(t, "project-1", "default", "alice")
	existing, err := lit.GetJob("train", lit.JobOptions{Teamspace: ts})
	require.NoErrorf(t, err,
		"GetJob returned error")
	assert.Falsef(t, existing.ID() != "job-1" || existing.Status() != "running",
		"unexpected fetched job: %s %s", existing.ID(), existing.Status())

	created, err := lit.RunJob("train-2", "cpu", "python train.py", lit.JobOptions{Teamspace: ts, Image: "ubuntu:22.04"})
	require.NoErrorf(t, err,
		"RunJob returned error")
	assert.Falsef(t, created.ID() != "job-2" || created.Status() != "pending",
		"unexpected created job: %s %s", created.ID(), created.Status())

	want := []string{
		"GET /v1/projects/-/-/jobs/train?projectId=project-1",
		"POST /v1/projects/project-1/jobs",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestJobRunValidatesComputeEnvironment(t *testing.T) {
	studio := mustStudio(t, "studio-1", "project-1")
	cases := []struct {
		name    string
		command string
		opts    lit.JobOptions
		want    string
	}{
		{
			name:    "missing image or studio",
			command: "python train.py",
			want:    "either image or studio must be provided",
		},
		{
			name:    "image and studio",
			command: "python train.py",
			opts:    lit.JobOptions{Image: "ubuntu:22.04", Studio: studio},
			want:    "image and studio are mutually exclusive",
		},
		{
			name:    "studio without command",
			command: "",
			opts:    lit.JobOptions{Studio: studio},
			want:    "command is required when using a studio",
		},
		{
			name:    "artifacts with studio",
			command: "python train.py",
			opts:    lit.JobOptions{Studio: studio, ArtifactsSource: "/outputs", ArtifactsDestination: "efs:data:outputs"},
			want:    "artifacts are only supported when using a custom image",
		},
		{
			name:    "missing artifact remote path",
			command: "python train.py",
			opts:    lit.JobOptions{Image: "ubuntu:22.04", ArtifactsSource: "/outputs"},
			want:    "artifacts require both local and remote paths",
		},
		{
			name:    "invalid artifact remote path",
			command: "python train.py",
			opts:    lit.JobOptions{Image: "ubuntu:22.04", ArtifactsSource: "/outputs", ArtifactsDestination: "data"},
			want:    "artifact remote path must be",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := lit.RunJob("train", "cpu", tc.command, tc.opts)
			assert.Falsef(t, err == nil || !strings.Contains(err.Error(), tc.want),
				"RunJob error = %v, want containing %q", err, tc.want)

		})
	}
}

func TestJobRunMapsAdvancedV2Options(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodPost || r.URL.Path != "/v1/projects/project-1/jobs",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		var body struct {
			Name string `json:"name"`
			Spec struct {
				Entrypoint                  string `json:"entrypoint"`
				ImageClusterCredentials     bool   `json:"imageClusterCredentials"`
				ImageSecretRef              string `json:"imageSecretRef"`
				RequestedRunDurationSeconds string `json:"requestedRunDurationSeconds"`
				PathMappings                []struct {
					ContainerPath  string `json:"containerPath"`
					ConnectionName string `json:"connectionName"`
					ConnectionPath string `json:"connectionPath"`
				} `json:"pathMappings"`
				Volumes []struct{} `json:"volumes"`
			} `json:"spec"`
		}
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode job body")
		assert.Falsef(t, body.Name != "train-advanced",
			"job name = %q, want train-advanced", body.Name)
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
		assert.Falsef(t, len(body.Spec.Volumes) != 0,
			"volumes length = %d, want 0", len(body.Spec.Volumes))

		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":        "job-advanced",
			"name":      "train-advanced",
			"projectId": "project-1",
			"state":     "pending",
			"spec": map[string]any{
				"image":                "registry.example/train:latest",
				"artifactsSource":      "/outputs",
				"artifactsDestination": "efs:data:outputs/run-1",
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	created, err := lit.RunJob(
		"train-advanced",
		"gpu",
		"train.py",
		lit.JobOptions{
			Teamspace:            mustTeamspace(t, "project-1", ""),
			Image:                "registry.example/train:latest",
			ImageCredentials:     "docker-secret",
			CloudAccountAuth:     true,
			Entrypoint:           "python",
			ArtifactsSource:      "/outputs",
			ArtifactsDestination: "efs:data:outputs/run-1",
			MaxRuntime:           7200,
			PathMappings: []lit.JobPathMapping{{
				ContainerPath:  "/data",
				ConnectionName: "dataset",
				ConnectionPath: "train",
			}},
		},
	)
	require.NoErrorf(t, err,
		"RunJob returned error")
	assert.Falsef(t, created.ID() != "job-advanced" || created.Status() != "pending",
		"unexpected created job: %s %s", created.ID(), created.Status())

	if got, want := created.ArtifactPath(), "/teamspace/efs_connections/data/outputs/run-1"; got != want {
		assert.Fail(t, fmt.Sprintf("created artifact path = %q, want %q", got, want))
	}
}

func TestJobRunMapsScratchDisksForStudioJobs(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodPost || r.URL.Path != "/v1/projects/project-1/jobs",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		var body struct {
			Name string `json:"name"`
			Spec struct {
				CloudspaceID string `json:"cloudspaceId"`
				Command      string `json:"command"`
				Volumes      []struct {
					Path      string `json:"path"`
					SizeGb    string `json:"sizeGb"`
					Ephemeral bool   `json:"ephemeral"`
				} `json:"volumes"`
			} `json:"spec"`
		}
		require.NoErrorf(t, json.NewDecoder(r.Body).Decode(&body),
			"decode job body")
		assert.Falsef(t, body.Name != "train-scratch" || body.Spec.CloudspaceID != "studio-1" || body.Spec.Command != "python train.py",
			"unexpected job body: %+v", body)
		assert.Falsef(t, len(body.Spec.Volumes) != 1,
			"volumes length = %d, want 1", len(body.Spec.Volumes))

		volume := body.Spec.Volumes[0]
		assert.Falsef(t, volume.Path != "/teamspace/scratch/cache" || volume.SizeGb != "100" || !volume.Ephemeral,
			"unexpected scratch volume: %+v", volume)

		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":        "job-scratch",
			"name":      "train-scratch",
			"projectId": "project-1",
			"state":     "pending",
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	created, err := lit.RunJob(
		"train-scratch",
		"gpu",
		"python train.py",
		lit.JobOptions{Studio: mustStudio(t, "studio-1", "project-1"), ScratchDisks: []lit.ScratchDisk{{Path: "cache", SizeGB: 100}}},
	)
	require.NoErrorf(t, err,
		"RunJob returned error")
	assert.Falsef(t, created.ID() != "job-scratch" || created.Status() != "pending",
		"unexpected created job: %s %s", created.ID(), created.Status())

}

func TestJobRunValidatesScratchDisks(t *testing.T) {
	studio := mustStudio(t, "studio-1", "project-1")
	cases := []struct {
		name string
		opts lit.JobOptions
		want string
	}{
		{
			name: "without studio",
			opts: lit.JobOptions{Image: "ubuntu:22.04", ScratchDisks: []lit.ScratchDisk{{Path: "cache", SizeGB: 100}}},
			want: "scratch_disks are only supported within a studio job",
		},
		{
			name: "too many disks",
			opts: lit.JobOptions{
				Studio: studio,
				ScratchDisks: []lit.ScratchDisk{
					{Path: "a", SizeGB: 1},
					{Path: "b", SizeGB: 1},
					{Path: "c", SizeGB: 1},
					{Path: "d", SizeGB: 1},
					{Path: "e", SizeGB: 1},
					{Path: "f", SizeGB: 1},
				},
			},
			want: "scratch_disk may only contain up to 5 elements",
		},
		{
			name: "too large",
			opts: lit.JobOptions{Studio: studio, ScratchDisks: []lit.ScratchDisk{{Path: "cache", SizeGB: 50001}}},
			want: "scratch_disk size cannot exceed 50TiB",
		},
		{
			name: "absolute outside scratch",
			opts: lit.JobOptions{Studio: studio, ScratchDisks: []lit.ScratchDisk{{Path: "/tmp/cache", SizeGB: 1}}},
			want: "scratch_disk paths must be relative to /teamspace/scratch",
		},
		{
			name: "parent path",
			opts: lit.JobOptions{Studio: studio, ScratchDisks: []lit.ScratchDisk{{Path: "../cache", SizeGB: 1}}},
			want: "scratch_disk path cannot contain '..'",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := lit.RunJob("train", "cpu", "python train.py", tc.opts)
			assert.Falsef(t, err == nil || !strings.Contains(err.Error(), tc.want),
				"RunJob error = %v, want containing %q", err, tc.want)

		})
	}
}

func TestJobRunUsesExplicitTeamspace(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "POST /v1/projects/project-1/jobs":
			var body struct {
				Name string `json:"name"`
				Spec struct {
					Command      string `json:"command"`
					ClusterID    string `json:"clusterId"`
					InstanceName string `json:"instanceName"`
				} `json:"spec"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode job body: %v", err))
			}
			if body.Name != "train-resolved" || body.Spec.Command != "python train.py" || body.Spec.ClusterID != "aws-us-east" || body.Spec.InstanceName != "cpu" {
				assert.Fail(t, fmt.Sprintf("unexpected job body: %+v", body))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "job-resolved",
				"name":      "train-resolved",
				"projectId": "project-1",
				"state":     "pending",
			})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	created, err := lit.RunJob(
		"train-resolved",
		"cpu",
		"python train.py",
		lit.JobOptions{Teamspace: mustTeamspace(t, "project-1", "default", "alice"), Cloud: "aws-us-east", Image: "ubuntu:22.04"},
	)
	require.NoErrorf(t, err,
		"RunJob returned error")
	assert.Falsef(t, created.ID() != "job-resolved" || created.TeamspaceID() != "project-1" || created.Teamspace() != "default" || created.OwnerName() != "alice",
		"unexpected created job: %+v", created)

	want := []string{
		"POST /v1/projects/project-1/jobs",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestJobRunRejectsMissingTeamspace(t *testing.T) {
	_, err := lit.RunJob("train", "cpu", "python train.py", lit.JobOptions{Image: "ubuntu:22.04"})
	assert.Falsef(t, err == nil || !strings.Contains(err.Error(), "requires teamspace or studio"),
		"RunJob error = %v, want teamspace validation", err)

}
