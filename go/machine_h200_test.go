package lit

import (
	"fmt"
	"testing"

	"github.com/stretchr/testify/require"

	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/models"
)

func TestH200MachineResolution(t *testing.T) {
	for _, tc := range []struct {
		count   int64
		machine Machine
	}{
		{1, MachineH200},
		{2, MachineH200X2},
		{4, MachineH200X4},
		{8, MachineH200X8},
	} {
		t.Run(fmt.Sprint(tc.count), func(t *testing.T) {
			name := "H200"
			if tc.count != 1 {
				name += fmt.Sprintf("_X_%d", tc.count)
			}
			require.Equal(t, fmt.Sprintf("lit-h200-%d", tc.count), string(tc.machine))
			require.Equal(t, string(tc.machine), machineSlugForFamily("H200", tc.count))
			require.Equal(t, tc.machine, machineFromString(name))

			// Every spelling the backend can hand back for this machine.
			for _, slug := range []string{
				fmt.Sprintf("lit-h200-%d", tc.count),
				fmt.Sprintf("lit-h200-141gb-%d", tc.count),
				fmt.Sprintf("lit-h200x-%d", tc.count),
			} {
				require.Equal(t, tc.machine, machineFromString(slug), slug)
				require.Equal(t, tc.machine, machineFromAccelerator(&models.V1ClusterAccelerator{
					Family: "H200", SlugMultiCloud: slug,
					Resources: &models.V1Resources{Gpu: tc.count},
				}), slug)
			}

			// A provider-specific accelerator falls back to the family slug.
			require.Equal(t, tc.machine, machineFromAccelerator(&models.V1ClusterAccelerator{
				Family: "H200", Slug: "provider-specific",
				Resources: &models.V1Resources{Gpu: tc.count},
			}))
		})
	}
	require.Empty(t, machineSlugForFamily("H200", 3))
}

func TestB200MachineResolution(t *testing.T) {
	for _, tc := range []struct {
		count   int64
		machine Machine
	}{
		{1, MachineB200},
		{8, MachineB200X8},
	} {
		t.Run(fmt.Sprint(tc.count), func(t *testing.T) {
			require.Equal(t, fmt.Sprintf("lit-b200-%d", tc.count), string(tc.machine))
			require.Equal(t, string(tc.machine), machineSlugForFamily("B200", tc.count))

			for _, slug := range []string{
				fmt.Sprintf("lit-b200-%d", tc.count),
				fmt.Sprintf("lit-b200x-%d", tc.count),
			} {
				require.Equal(t, tc.machine, machineFromString(slug), slug)
			}
			require.Equal(t, tc.machine, machineFromAccelerator(&models.V1ClusterAccelerator{
				Family: "B200", Slug: "provider-specific",
				Resources: &models.V1Resources{Gpu: tc.count},
			}))
		})
	}
	require.Equal(t, MachineB200X8, machineFromString("lit-b200-180gb-8"))
	require.Empty(t, machineSlugForFamily("B200", 4))
}
