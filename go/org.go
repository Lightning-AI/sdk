package lit

import (
	"context"
	"errors"
	"fmt"
	"os"

	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/organizations_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/projects_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/models"
	"github.com/lightning-ai/sdk/go/internal/sdkclient"
)

// Organization represents a Lightning organization.
type Organization struct {
	id                  string
	name                string
	defaultCloudAccount string
}

type orgOptions struct {
	id                  string
	defaultCloudAccount string
}

// OrganizationOptions configures organization lookup.
type OrganizationOptions struct {
	// ID resolves an existing organization directly without looking it up by name.
	ID string
	// DefaultCloudAccount stores the preferred cloud account for the organization handle.
	DefaultCloudAccount string
}

// GetOrganization returns an organization by name or ID.
func GetOrganization(name string, opts ...OrganizationOptions) (*Organization, error) {
	resolved := applyOrgOptions(opts...)
	if name == "" {
		name = os.Getenv("LIGHTNING_ORG")
	}
	if name == "" && resolved.id == "" {
		return nil, errors.New("org requires name or ID")
	}
	if resolved.id != "" && name != "" {
		return &Organization{id: resolved.id, name: name, defaultCloudAccount: resolved.defaultCloudAccount}, nil
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	if resolved.id != "" {
		resp, err := api.OrganizationsService.OrganizationsServiceGetOrganization(
			organizations_service.NewOrganizationsServiceGetOrganizationParamsWithContext(context.Background()).WithID(resolved.id),
		)
		if err != nil {
			return nil, err
		}
		return orgFromModel(resp.Payload), nil
	}
	organization, err := findOrgModel(api, name)
	if err != nil {
		return nil, err
	}
	return orgFromModel(organization), nil
}

// ID returns the organization ID.
func (o *Organization) ID() string {
	if o == nil {
		return ""
	}
	return o.id
}

// Name returns the organization name.
func (o *Organization) Name() string {
	if o == nil {
		return ""
	}
	return o.name
}

// DefaultCloudAccount returns the organization's preferred cloud account ID.
func (o *Organization) DefaultCloudAccount() string {
	if o == nil {
		return ""
	}
	return o.defaultCloudAccount
}

// String returns a compact human-readable representation.
func (o *Organization) String() string {
	if o == nil {
		return "Organization(name=)"
	}
	return fmt.Sprintf("Organization(name=%s)", o.Name())
}

// Equal reports whether two organization handles refer to the same public state.
func (o *Organization) Equal(other *Organization) bool {
	if o == nil || other == nil {
		return o == other
	}
	return o.ID() == other.ID() && o.Name() == other.Name()
}

// CreateTeamspace creates a teamspace owned by the organization.
func (o *Organization) CreateTeamspace(name string) (*Teamspace, error) {
	if o == nil || o.ID() == "" {
		return nil, errors.New("org create teamspace requires ID")
	}
	return CreateTeamspace(name, TeamspaceOptions{Owner: o})
}

// Teamspaces lists teamspaces owned by the organization.
func (o *Organization) Teamspaces() ([]*Teamspace, error) {
	if o.ID() == "" {
		return nil, errors.New("org teamspaces requires ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	filterByUserID := true
	resp, err := api.ProjectsService.ProjectsServiceListMemberships(
		projects_service.NewProjectsServiceListMembershipsParamsWithContext(context.Background()).
			WithFilterByUserID(&filterByUserID).
			WithOrganizationID(&o.id),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("list org teamspaces returned empty payload")
	}
	var result []*Teamspace
	for _, membership := range resp.Payload.Memberships {
		if membership == nil || membership.OwnerID != o.ID() {
			continue
		}
		item, err := GetTeamspace(membership.Name, TeamspaceOptions{ID: membership.ProjectID, Owner: o})
		if err != nil {
			return nil, err
		}
		result = append(result, item)
	}
	return result, nil
}

func applyOrgOptions(opts ...OrganizationOptions) orgOptions {
	var resolved orgOptions
	if len(opts) > 0 {
		resolved.id = opts[0].ID
		resolved.defaultCloudAccount = opts[0].DefaultCloudAccount
	}
	return resolved
}

func orgFromModel(model *models.V1Organization) *Organization {
	if model == nil {
		return nil
	}
	return &Organization{id: model.ID, name: model.Name, defaultCloudAccount: model.PreferredCluster}
}
