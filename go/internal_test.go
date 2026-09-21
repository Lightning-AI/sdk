package lit

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type ownerForTest struct {
	id   string
	name string
}

func (o ownerForTest) ID() string { return o.id }

func (o ownerForTest) Name() string { return o.name }

func (o ownerForTest) CreateTeamspace(string) (*Teamspace, error) { return nil, nil }

func (o ownerForTest) Teamspaces() ([]*Teamspace, error) { return nil, nil }

func TestTeamspaceKeepsInternalOwner(t *testing.T) {
	ts, err := GetTeamspace("default", TeamspaceOptions{
		ID:    "project-1",
		Owner: ownerForTest{name: "alice"},
	})
	require.NoErrorf(t, err,
		"GetTeamspace returned error")
	assert.Falsef(t, ts.owner.ID() != "" || ts.owner.Name() != "alice",
		"unexpected teamspace owner: %+v", ts.owner)

}

func TestStudioKeepsInternalTeamspaceOwnerChain(t *testing.T) {
	ts, err := GetTeamspace("default", TeamspaceOptions{
		ID:    "project-1",
		Owner: ownerForTest{name: "alice"},
	})
	require.NoErrorf(t, err,
		"GetTeamspace returned error")

	s, err := GetStudio("dev", StudioOptions{
		ID:        "studio-1",
		Teamspace: ts,
	})
	require.NoErrorf(t, err,
		"GetStudio returned error")
	assert.Falsef(t, s.teamspace.id != "project-1" || s.teamspace.name != "default" || s.teamspace.ownerName != "alice",
		"unexpected studio teamspace chain: %+v", s.teamspace)

}

// An explicit Cloud wins, but an absent one must not wipe out the default the
// teamspace or studio already supplied.
func TestOptionsKeepInheritedCloudAccount(t *testing.T) {
	ts, err := GetTeamspace("default", TeamspaceOptions{ID: "project-1", DefaultCloudAccount: "teamspace-account"})
	require.NoError(t, err)

	assert.Equal(t, "teamspace-account", applyJobOptions(JobOptions{Teamspace: ts}).cloud)
	assert.Equal(t, "explicit-account", applyJobOptions(JobOptions{Teamspace: ts, Cloud: "explicit-account"}).cloud)
	assert.Equal(t, "teamspace-account", applyMMTOptions(MMTOptions{Teamspace: ts}).cloud)
	assert.Equal(t, "explicit-account", applyMMTOptions(MMTOptions{Teamspace: ts, Cloud: "explicit-account"}).cloud)
}
