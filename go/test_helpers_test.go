package lit_test

import (
	"encoding/json"
	"errors"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	lit "github.com/lightning-ai/sdk/go"
)

// writeBlobUploadResponse answers a blob-upload request with one presigned URL
// for path, optionally carrying headers the client must replay on the PUT.
func writeBlobUploadResponse(w http.ResponseWriter, path, signedURL string, headers map[string]string) {
	urlEntry := map[string]any{"url": signedURL}
	if len(headers) > 0 {
		urlEntry["headers"] = headers
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{
		"expires_at": "2026-01-01T00:00:00Z",
		"results":    []map[string]any{{"path": path, "urls": []map[string]any{urlEntry}}},
	})
}

// decodeBlobUploadBatch decodes the body of a blob-upload or blob-complete
// request into its cluster id and blob paths. It runs on the test server's
// handler goroutine, so failures must stay non-fatal (no require/FailNow).
func decodeBlobUploadBatch(t *testing.T, r *http.Request) (clusterID string, paths []string) {
	t.Helper()
	var body struct {
		ClusterID string `json:"cluster_id"`
		Blobs     []struct {
			Path string `json:"path"`
		} `json:"blobs"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		assert.Failf(t, "decode blob upload body", "%v", err)
		return "", nil
	}
	for _, blob := range body.Blobs {
		paths = append(paths, blob.Path)
	}
	return body.ClusterID, paths
}

type testOwner struct {
	id   string
	name string
}

func (o testOwner) ID() string { return o.id }

func (o testOwner) Name() string { return o.name }

func (o testOwner) CreateTeamspace(string) (*lit.Teamspace, error) {
	return nil, errors.New("not implemented")
}

func (o testOwner) Teamspaces() ([]*lit.Teamspace, error) {
	return nil, errors.New("not implemented")
}

func mustUser(t *testing.T, id, name string) *lit.User {
	t.Helper()
	result, err := lit.GetUser(name, lit.UserOptions{ID: id})
	require.NoError(t, err,
		err)

	return result
}

func mustOrg(t *testing.T, id, name string) *lit.Organization {
	t.Helper()
	result, err := lit.GetOrganization(name, lit.OrganizationOptions{ID: id})
	require.NoError(t, err,
		err)

	return result
}

func mustTeamspace(t *testing.T, id, name string, ownerName ...string) *lit.Teamspace {
	t.Helper()
	opts := lit.TeamspaceOptions{ID: id}
	if len(ownerName) > 0 {
		opts.Owner = testOwner{name: ownerName[0]}
	}
	result, err := lit.GetTeamspace(name, opts)
	require.NoError(t, err,
		err)

	return result
}

func mustStudio(t *testing.T, id, teamspaceID string, options ...lit.StudioOptions) *lit.Studio {
	t.Helper()
	opts := lit.StudioOptions{ID: id, Teamspace: mustTeamspace(t, teamspaceID, "")}
	if len(options) > 0 {
		opts = options[0]
		opts.ID = id
		if opts.Teamspace == nil {
			opts.Teamspace = mustTeamspace(t, teamspaceID, "")
		}
	}
	result, err := lit.GetStudio("", opts)
	require.NoError(t, err,
		err)

	return result
}

func mustJob(t *testing.T, id, name, teamspaceID string, studioIDOrOptions ...any) *lit.Job {
	t.Helper()
	opts := lit.JobOptions{ID: id, Teamspace: mustTeamspace(t, teamspaceID, "")}
	for _, item := range studioIDOrOptions {
		switch value := item.(type) {
		case string:
			opts.Studio = mustStudio(t, value, teamspaceID)
		case lit.JobOptions:
			studio := opts.Studio
			opts = value
			if opts.Studio == nil {
				opts.Studio = studio
			}
			if opts.Teamspace == nil {
				opts.Teamspace = mustTeamspace(t, teamspaceID, "")
			}
			opts.ID = id
		}
	}
	result, err := lit.GetJob(name, opts)
	require.NoError(t, err,
		err)

	return result
}

func mustMMT(t *testing.T, id, name, teamspaceID string, options ...lit.MMTOptions) *lit.MMT {
	t.Helper()
	opts := lit.MMTOptions{ID: id, Teamspace: mustTeamspace(t, teamspaceID, "")}
	if len(options) > 0 {
		opts = options[0]
		opts.ID = id
		if opts.Teamspace == nil && opts.Studio == nil {
			opts.Teamspace = mustTeamspace(t, teamspaceID, "")
		}
	}
	result, err := lit.GetMMT(name, opts)
	require.NoError(t, err,
		err)

	return result
}
