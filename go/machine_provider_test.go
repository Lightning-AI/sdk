package lit_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/stretchr/testify/require"

	lit "github.com/lightning-ai/sdk/go"
)

func TestH200RequestsUseDestinationProvider(t *testing.T) {
	for _, provider := range []string{"MACHINE", "AWS", "GCP"} {
		t.Run(provider, func(t *testing.T) {
			want := "lit-h200x-2"
			if provider == "MACHINE" {
				want = "lit-h200-141gb-2"
			}
			var requests int
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "application/json")
				if r.Method == "GET" && strings.HasSuffix(r.URL.Path, "/clusters") {
					if provider != "MACHINE" && strings.Contains(r.URL.Path, "/projects/") {
						_, _ = w.Write([]byte(`{"clusters":[]}`))
						return
					}
					_ = json.NewEncoder(w).Encode(map[string]any{"clusters": []any{
						map[string]any{"id": "custom-account", "spec": map[string]any{"driver": provider}},
					}})
					return
				}
				var body map[string]any
				require.NoError(t, json.NewDecoder(r.Body).Decode(&body))
				requests++
				switch {
				case strings.HasSuffix(r.URL.Path, "/cloudspaces"):
					require.Equal(t, want, body["computeName"])
					_ = json.NewEncoder(w).Encode(map[string]any{"id": "studio", "name": "dev", "projectId": "project-1", "clusterId": "custom-account"})
				case strings.HasSuffix(r.URL.Path, "/start"), strings.HasSuffix(r.URL.Path, "/codeconfig"):
					require.Equal(t, want, body["computeConfig"].(map[string]any)["name"])
					_, _ = w.Write([]byte(`{}`))
				case strings.HasSuffix(r.URL.Path, "/jobs"), strings.HasSuffix(r.URL.Path, "/multi-machine-jobs"):
					require.Equal(t, want, body["spec"].(map[string]any)["instanceName"])
					_ = json.NewEncoder(w).Encode(map[string]any{"id": "job", "name": "train", "projectId": "project-1", "spec": body["spec"]})
				default:
					t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
					http.Error(w, "unexpected", 500)
				}
			}))
			defer server.Close()
			t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
			t.Setenv("LIGHTNING_USER_ID", "test-user")
			t.Setenv("LIGHTNING_API_KEY", "test-key")
			t.Setenv("LIGHTNING_DEBUG", "0")
			ts, err := lit.GetTeamspace("", lit.TeamspaceOptions{ID: "project-1", DefaultCloudAccount: "custom-account"})
			require.NoError(t, err)
			spot := false
			s, err := lit.CreateStudio("dev", lit.StudioOptions{Teamspace: ts, Machine: lit.MachineH200X2, Interruptible: &spot})
			require.NoError(t, err)
			require.NoError(t, s.Start(lit.StartStudioOptions{Machine: lit.MachineH200X2, Interruptible: &spot}))
			require.NoError(t, s.SwitchMachine(lit.MachineH200X2, lit.SwitchMachineOptions{Cloud: "custom-account"}))
			_, err = lit.RunJob("train", lit.MachineH200X2, "true", lit.JobOptions{Teamspace: ts, Image: "ubuntu"})
			require.NoError(t, err)
			_, err = lit.RunMMT("train", 2, lit.MachineH200X2, "true", lit.MMTOptions{Teamspace: ts, Image: "ubuntu"})
			require.NoError(t, err)
			require.Equal(t, 5, requests)
		})
	}
}
