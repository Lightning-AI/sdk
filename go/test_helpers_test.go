package lit_test

import (
	"errors"
	"testing"

	"github.com/stretchr/testify/require"

	lit "github.com/lightning-ai/sdk/go"
)

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
