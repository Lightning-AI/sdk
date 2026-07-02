package lit

import (
	"context"
	"errors"
	"fmt"
	"os"

	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/client/organizations_service"
	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/client/projects_service"
	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/client/secret_service"
	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/models"
	"github.com/gridai/lightning-sdk/go/internal/sdkclient"
)

// User represents a Lightning user.
type User struct {
	id   string
	name string
}

type userOptions struct {
	id string
}

// UserOptions configures user lookup.
type UserOptions struct {
	ID string
}

// GetUser returns a user by name or ID.
func GetUser(name string, opts ...UserOptions) (*User, error) {
	resolved := applyUserOptions(opts...)
	if name == "" {
		name = os.Getenv("LIGHTNING_USERNAME")
	}
	if name == "" && resolved.id == "" {
		return nil, errors.New("user requires name or ID")
	}
	if resolved.id != "" {
		return &User{id: resolved.id, name: name}, nil
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	id, username, err := findUserByName(api, name)
	if err != nil {
		return nil, err
	}
	return &User{id: id, name: username}, nil
}

// ID returns the user ID.
func (u *User) ID() string {
	if u == nil {
		return ""
	}
	return u.id
}

// Name returns the username.
func (u *User) Name() string {
	if u == nil {
		return ""
	}
	return u.name
}

// String returns a compact human-readable representation.
func (u *User) String() string {
	if u == nil {
		return "User(name=)"
	}
	return fmt.Sprintf("User(name=%s)", u.Name())
}

// Equal reports whether two user handles refer to the same public state.
func (u *User) Equal(other *User) bool {
	if u == nil || other == nil {
		return u == other
	}
	return u.ID() == other.ID() && u.Name() == other.Name()
}

// CreateTeamspace creates a teamspace owned by the user.
func (u *User) CreateTeamspace(name string) (*Teamspace, error) {
	if u == nil || u.ID() == "" {
		return nil, errors.New("user create teamspace requires ID")
	}
	return CreateTeamspace(name, TeamspaceOptions{Owner: u})
}

// Teamspaces lists teamspaces owned by the user.
func (u *User) Teamspaces() ([]*Teamspace, error) {
	if u.ID() == "" {
		return nil, errors.New("user teamspaces requires ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	filterByUserID := true
	resp, err := api.ProjectsService.ProjectsServiceListMemberships(
		projects_service.NewProjectsServiceListMembershipsParamsWithContext(context.Background()).
			WithFilterByUserID(&filterByUserID),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("list user teamspaces returned empty payload")
	}
	var result []*Teamspace
	for _, membership := range resp.Payload.Memberships {
		if membership == nil || membership.OwnerID != u.ID() {
			continue
		}
		item, err := GetTeamspace(membership.Name, TeamspaceOptions{ID: membership.ProjectID, Owner: u})
		if err != nil {
			return nil, err
		}
		result = append(result, item)
	}
	return result, nil
}

// Organizations lists organizations visible to the user.
func (u *User) Organizations() ([]*Organization, error) {
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	resp, err := api.OrganizationsService.OrganizationsServiceListOrganizations(
		organizations_service.NewOrganizationsServiceListOrganizationsParamsWithContext(context.Background()),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("list user organizations returned empty payload")
	}
	var result []*Organization
	for _, organization := range resp.Payload.Organizations {
		if organization == nil {
			continue
		}
		item, err := GetOrganization(organization.Name, OrganizationOptions{ID: organization.ID, DefaultCloudAccount: organization.PreferredCluster})
		if err != nil {
			return nil, err
		}
		result = append(result, item)
	}
	return result, nil
}

// Secrets returns redacted user secret names.
func (u *User) Secrets() (map[string]string, error) {
	if u == nil {
		return nil, errors.New("user secrets requires user")
	}
	secrets, err := u.listSecrets()
	if err != nil {
		return nil, err
	}
	return redactedSecrets(secrets), nil
}

// SetSecret creates or updates a user secret.
func (u *User) SetSecret(key, value string) error {
	if u == nil {
		return errors.New("user set secret requires user")
	}
	if !validSecretName(key) {
		return errors.New("secret keys must only contain alphanumeric characters and underscores and not begin with a number")
	}
	secrets, err := u.listSecrets()
	if err != nil {
		return err
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	for _, secret := range secrets {
		if secret != nil && secret.Name == key {
			_, err := api.SecretService.SecretServiceUpdateUserSecret(
				secret_service.NewSecretServiceUpdateUserSecretParamsWithContext(context.Background()).
					WithID(secret.ID).
					WithBody(&models.SecretServiceUpdateUserSecretBody{Value: value}),
			)
			return err
		}
	}
	_, err = api.SecretService.SecretServiceCreateUserSecret(
		secret_service.NewSecretServiceCreateUserSecretParamsWithContext(context.Background()).
			WithBody(&models.V1CreateUserSecretRequest{Name: key, Value: value}),
	)
	return err
}

func (u *User) listSecrets() ([]*models.V1Secret, error) {
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	resp, err := api.SecretService.SecretServiceListUserSecrets(
		secret_service.NewSecretServiceListUserSecretsParamsWithContext(context.Background()),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("list user secrets returned empty payload")
	}
	return resp.Payload.Secrets, nil
}

func applyUserOptions(opts ...UserOptions) userOptions {
	var resolved userOptions
	if len(opts) > 0 {
		resolved.id = opts[0].ID
	}
	return resolved
}
