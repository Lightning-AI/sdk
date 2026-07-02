package lit

import (
	"context"
	"fmt"

	sdkapi "github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/client"
	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/client/organizations_service"
	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/client/projects_service"
	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/client/user_service"
	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/models"
)

func findUserByName(api *sdkapi.LightningSdkAPI, name string) (string, string, error) {
	resp, err := api.UserService.UserServiceSearchUsers(
		user_service.NewUserServiceSearchUsersParamsWithContext(context.Background()).WithQuery(&name),
	)
	if err != nil {
		return "", "", err
	}
	if resp.Payload == nil {
		return "", "", fmt.Errorf("search users returned empty payload")
	}
	for _, candidate := range resp.Payload.Users {
		if candidate != nil && candidate.Username == name {
			return candidate.ID, candidate.Username, nil
		}
	}
	return "", "", fmt.Errorf("user %q not found", name)
}

func findOrgModel(api *sdkapi.LightningSdkAPI, name string) (*models.V1Organization, error) {
	resp, err := api.OrganizationsService.OrganizationsServiceListOrganizations(
		organizations_service.NewOrganizationsServiceListOrganizationsParamsWithContext(context.Background()),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("list organizations returned empty payload")
	}
	for _, candidate := range resp.Payload.Organizations {
		if candidate != nil && candidate.Name == name {
			return candidate, nil
		}
	}
	return nil, fmt.Errorf("org %q not found", name)
}

func findTeamspaceID(api *sdkapi.LightningSdkAPI, name, ownerID string, organization bool) (string, error) {
	filterByUserID := true
	params := projects_service.NewProjectsServiceListMembershipsParamsWithContext(context.Background()).
		WithFilterByUserID(&filterByUserID)
	if organization {
		params = params.WithOrganizationID(&ownerID)
	}
	resp, err := api.ProjectsService.ProjectsServiceListMemberships(params)
	if err != nil {
		return "", err
	}
	if resp.Payload == nil {
		return "", fmt.Errorf("list teamspace memberships returned empty payload")
	}
	for _, membership := range resp.Payload.Memberships {
		if membership != nil && membership.Name == name && membership.OwnerID == ownerID {
			return membership.ProjectID, nil
		}
	}
	return "", fmt.Errorf("teamspace %q not found", name)
}
