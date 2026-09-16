package lit

import (
	"context"
	"fmt"
	"strings"

	sdkapi "github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/cluster_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/models"
)

func resolveMachineComputeName(api *sdkapi.LightningSdkAPI, machine, teamspaceID, cloud string) (string, error) {
	canonical := string(machineFromString(machine))
	if (canonical != string(MachineH200) && canonical != string(MachineH200X2) && canonical != string(MachineH200X4) && canonical != string(MachineH200X8)) || cloud == "" {
		return machine, nil
	}
	project, err := api.ClusterService.ClusterServiceListProjectClusters(
		cluster_service.NewClusterServiceListProjectClustersParamsWithContext(context.Background()).WithProjectID(teamspaceID),
	)
	if err != nil {
		return "", err
	}
	clusters := project.Payload.Clusters
	for _, cluster := range clusters {
		if cluster != nil && cluster.ID == cloud {
			return h200ComputeName(canonical, cluster), nil
		}
	}
	global, err := api.ClusterService.ClusterServiceListClusters(
		cluster_service.NewClusterServiceListClustersParamsWithContext(context.Background()).WithProjectID(&teamspaceID),
	)
	if err != nil {
		return "", err
	}
	for _, cluster := range global.Payload.Clusters {
		if cluster != nil && cluster.ID == cloud {
			return h200ComputeName(canonical, cluster), nil
		}
	}
	return "", fmt.Errorf("cloud account %q not found for H200 machine resolution", cloud)
}

func h200ComputeName(machine string, cluster *models.V1ExternalCluster) string {
	if cluster.Spec != nil && ((cluster.Spec.Driver != nil && *cluster.Spec.Driver == models.V1CloudProviderMACHINE) || (cluster.Spec.Driver == nil && cluster.Spec.MachineV1 != nil)) {
		return strings.Replace(machine, "lit-h200x-", "lit-h200-141gb-", 1)
	}
	return machine
}
