package lit_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	lit "github.com/gridai/lightning-sdk/go"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestJobLifecycleUsesV2Routes(t *testing.T) {
	var serverURL string
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "PUT /v1/projects/project-1/jobs/job-1":
			var body struct {
				State string `json:"state"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode stop body: %v", err))
			}
			if body.State != "stopped" {
				assert.Fail(t, fmt.Sprintf("state = %q, want stopped", body.State))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "job-1",
				"name":      "train",
				"projectId": "project-1",
				"state":     "stopped",
			})
		case "DELETE /v1/projects/project-1/jobs/job-1":
			if r.URL.Query().Get("cloudspaceId") != "studio-1" {
				assert.Fail(t, fmt.Sprintf("cloudspaceId = %q, want studio-1", r.URL.Query().Get("cloudspaceId")))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{})
		case "GET /v1/projects/project-1/jobs/job-1/download-logs":
			_ = json.NewEncoder(w).Encode(map[string]any{"url": serverURL + "/logs/job-1"})
		case "GET /logs/job-1":
			w.Header().Set("Content-Type", "text/plain")
			_, _ = w.Write([]byte("[2026-06-16T10:00:00Z] first line\n[2026-06-16T10:00:01Z] second line\n"))
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	serverURL = server.URL
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	j := func() *lit.Job {
		return mustJob(t, "job-1", "train", "project-1", "studio-1", lit.JobOptions{Status: "running"})
	}()
	require.NoErrorf(t, j.Stop(),
		"job.Stop returned error")
	assert.Falsef(t, j.Status() != "stopped",
		"job status = %q, want stopped", j.Status())
	require.NoErrorf(t, j.Delete(),
		"job.Delete returned error")

	logs, err := j.Logs()
	require.NoErrorf(t, err,
		"job.Logs returned error")
	assert.Falsef(t, logs != "first line\nsecond line\n",
		"logs = %q", logs)

	want := []string{
		"PUT /v1/projects/project-1/jobs/job-1",
		"DELETE /v1/projects/project-1/jobs/job-1?cloudspaceId=studio-1",
		"GET /v1/projects/project-1/jobs/job-1/download-logs",
		"GET /logs/job-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestJobWaitPollsUntilTerminalState(t *testing.T) {
	var seen []string
	polls := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/projects/project-1/jobs/job-1",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		polls++
		state := "running"
		if polls == 2 {
			state = "completed"
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":        "job-1",
			"name":      "train",
			"projectId": "project-1",
			"state":     state,
			"totalCost": 1.25,
			"spec": map[string]any{
				"instanceName": "cpu",
				"command":      "python train.py",
				"image":        "ubuntu:22.04",
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	j := mustJob(t, "job-1", "train", "project-1", lit.JobOptions{Status: "running"})
	require.NoErrorf(t, j.Wait(lit.JobWaitOptions{Interval: time.Millisecond}),
		"job.Wait returned error")
	assert.Falsef(t, j.Status() != "completed" || j.Machine() != "cpu" || j.Command() != "python train.py" || j.TotalCost() != 1.25,
		"unexpected waited job: %+v", j)

	want := []string{
		"GET /v1/projects/project-1/jobs/job-1",
		"GET /v1/projects/project-1/jobs/job-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestMMTLifecycleUsesV2Routes(t *testing.T) {
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "PUT /v1/projects/project-1/multi-machine-jobs/mmt-1":
			var body struct {
				DesiredState string `json:"desiredState"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				assert.Fail(t, fmt.Sprintf("decode stop body: %v", err))
			}
			if body.DesiredState != "MultiMachineJob_STATE_STOP" {
				assert.Fail(t, fmt.Sprintf("desiredState = %q, want stop enum", body.DesiredState))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":        "mmt-1",
				"name":      "dist-train",
				"projectId": "project-1",
				"machines":  4,
				"state":     "MultiMachineJob_STATE_STOPPED",
			})
		case "DELETE /v1/projects/project-1/multi-machine-jobs/mmt-1":
			_ = json.NewEncoder(w).Encode(map[string]any{})
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	m := func() *lit.MMT {
		return mustMMT(t, "mmt-1", "dist-train", "project-1", lit.MMTOptions{NumMachines: 4, Status: "running"})
	}()
	require.NoErrorf(t, m.Stop(),
		"mmt.Stop returned error")
	assert.Falsef(t, m.Status() != "MultiMachineJob_STATE_STOPPED",
		"mmt status = %q, want stopped enum", m.Status())
	require.NoErrorf(t, m.Delete(),
		"mmt.Delete returned error")

	want := []string{
		"PUT /v1/projects/project-1/multi-machine-jobs/mmt-1",
		"DELETE /v1/projects/project-1/multi-machine-jobs/mmt-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestMMTWaitPollsUntilTerminalState(t *testing.T) {
	var seen []string
	polls := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/projects/project-1/multi-machine-jobs/mmt-1",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		polls++
		state := "MultiMachineJob_STATE_RUNNING"
		if polls == 2 {
			state = "MultiMachineJob_STATE_COMPLETED"
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":        "mmt-1",
			"name":      "dist-train",
			"projectId": "project-1",
			"machines":  4,
			"state":     state,
			"totalCost": 9.75,
			"spec": map[string]any{
				"instanceName": "gpu",
				"command":      "torchrun train.py",
				"image":        "pytorch/pytorch:latest",
			},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	m := func() *lit.MMT {
		return mustMMT(t, "mmt-1", "dist-train", "project-1", lit.MMTOptions{Status: "MultiMachineJob_STATE_RUNNING"})
	}()
	require.NoErrorf(t, m.Wait(lit.MMTWaitOptions{Interval: time.Millisecond}),
		"mmt.Wait returned error")
	assert.Falsef(t, m.Status() != "MultiMachineJob_STATE_COMPLETED" || m.NumMachines() != 4 || m.Machine() != "gpu" || m.Command() != "torchrun train.py" || m.TotalCost() != 9.75,
		"unexpected waited mmt: %+v", m)

	want := []string{
		"GET /v1/projects/project-1/multi-machine-jobs/mmt-1",
		"GET /v1/projects/project-1/multi-machine-jobs/mmt-1",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestMMTListsSubJobsWithV2Route(t *testing.T) {
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
					"totalCost":         2.5,
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
	m := mustMMT(t, "mmt-1", "dist-train", "project-1", lit.MMTOptions{Teamspace: ts, NumMachines: 4})
	machines, err := m.Machines()
	require.NoErrorf(t, err,
		"mmt.Machines returned error")
	assert.Falsef(t, len(machines) != 1 || machines[0].ID() != "job-rank-0" || machines[0].Machine() != "gpu" || machines[0].Command() != "torchrun train.py" || machines[0].TotalCost() != 2.5,
		"unexpected mmt machines: %+v", machines)

	if got, want := machines[0].Link(), "https://lightning.ai/alice/default/jobs/dist-train-0"; got != want {
		assert.Fail(t, fmt.Sprintf("mmt subjob link = %q, want %q", got, want))
	}

	want := []string{"GET /v1/projects/project-1/jobs?multiMachineJobId=mmt-1"}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}

func TestMMTLogsUseFirstSubJobLogs(t *testing.T) {
	var serverURL string
	var seen []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.RequestURI())
		w.Header().Set("Content-Type", "application/json")
		switch r.Method + " " + r.URL.Path {
		case "GET /v1/projects/project-1/jobs":
			if r.URL.Query().Get("multiMachineJobId") != "mmt-1" {
				assert.Fail(t, fmt.Sprintf("multiMachineJobId = %q, want mmt-1", r.URL.Query().Get("multiMachineJobId")))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"jobs": []map[string]any{
					{
						"id":        "job-rank-0",
						"name":      "dist-train-0",
						"projectId": "project-1",
						"state":     "completed",
					},
				},
			})
		case "GET /v1/projects/project-1/jobs/job-rank-0/download-logs":
			_ = json.NewEncoder(w).Encode(map[string]any{"url": serverURL + "/logs/job-rank-0"})
		case "GET /logs/job-rank-0":
			w.Header().Set("Content-Type", "text/plain")
			_, _ = w.Write([]byte("[2026-06-16T10:00:00Z] rank 0 line\n"))
		default:
			assert.Fail(t, fmt.Sprintf("unexpected request: %s %s", r.Method, r.URL.RequestURI()))
		}
	}))
	serverURL = server.URL
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)

	m := mustMMT(t, "mmt-1", "dist-train", "project-1")
	logs, err := m.Logs()
	require.NoErrorf(t, err,
		"mmt.Logs returned error")
	assert.Falsef(t, logs != "rank 0 line\n",
		"logs = %q", logs)

	want := []string{
		"GET /v1/projects/project-1/jobs?multiMachineJobId=mmt-1",
		"GET /v1/projects/project-1/jobs/job-rank-0/download-logs",
		"GET /logs/job-rank-0",
	}
	assert.Falsef(t, len(seen) != len(want),
		"seen requests = %v, want %v", seen, want)

	for i := range want {
		assert.Falsef(t, seen[i] != want[i],
			"request %d = %q, want %q", i, seen[i], want[i])

	}
}
