package lit

import (
	"fmt"
	"testing"

	"github.com/stretchr/testify/require"

	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/models"
)

func TestH200MachineResolution(t *testing.T) {
	for _, tc := range []struct {
		count     int64
		cloud     Machine
		baremetal Machine
	}{
		{1, MachineH200, MachineH200141GB},
		{2, MachineH200X2, MachineH200141GBX2},
		{4, MachineH200X4, MachineH200141GBX4},
		{8, MachineH200X8, MachineH200141GBX8},
	} {
		t.Run(fmt.Sprint(tc.count), func(t *testing.T) {
			require.Equal(t, string(tc.cloud), machineSlugForFamily("H200", tc.count))
			for _, baremetal := range []bool{false, true} {
				name, slug, machine := "H200", fmt.Sprintf("lit-h200x-%d", tc.count), tc.cloud
				if baremetal {
					name, slug, machine = "H200_141GB", fmt.Sprintf("lit-h200-141gb-%d", tc.count), tc.baremetal
				}
				if tc.count != 1 {
					name += fmt.Sprintf("_X_%d", tc.count)
				}
				require.Equal(t, slug, string(machine))
				require.Equal(t, machine, machineFromString(name))
				require.Equal(t, machine, machineFromString(slug))
				require.Equal(t, machine, machineFromAccelerator(&models.V1ClusterAccelerator{
					Family: "H200", SlugMultiCloud: slug,
					Resources: &models.V1Resources{Gpu: tc.count},
				}))
			}
			require.Equal(t, tc.cloud, machineFromAccelerator(&models.V1ClusterAccelerator{
				Family: "H200", Slug: "provider-specific",
				Resources: &models.V1Resources{Gpu: tc.count},
			}))
		})
	}
	require.Empty(t, machineSlugForFamily("H200", 3))
}
