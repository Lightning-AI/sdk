package lit

import (
	"fmt"
	"strings"

	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/models"
)

// Machine identifies a Lightning machine type.
type Machine string

// Known Lightning machine types.
const (
	MachineCPUSmall      Machine = "cpu-2"
	MachineCPU           Machine = "cpu-4"
	MachineCPUX2         Machine = "cpu-2"
	MachineCPUX4         Machine = "cpu-4"
	MachineCPUX8         Machine = "cpu-8"
	MachineCPUX16        Machine = "cpu-16"
	MachineDataPrep      Machine = "data-prep-mid"
	MachineDataPrepMax   Machine = "data-prep-max-large"
	MachineDataPrepUltra Machine = "data-prep-ultra-extra-large"
	MachineT4Small       Machine = "lit-t4-1-small"
	MachineT4            Machine = "lit-t4-1"
	MachineT4X2          Machine = "lit-t4-2"
	MachineT4X4          Machine = "lit-t4-4"
	MachineT4X8          Machine = "lit-t4-8"
	MachineL4            Machine = "lit-l4-1"
	MachineL4X2          Machine = "lit-l4-2"
	MachineL4X4          Machine = "lit-l4-4"
	MachineL4X8          Machine = "lit-l4-8"
	MachineL40S          Machine = "lit-l40s-1"
	MachineL40SX2        Machine = "lit-l40s-2"
	MachineL40SX4        Machine = "lit-l40s-4"
	MachineL40SX8        Machine = "lit-l40s-8"
	MachineRTXP6000      Machine = "lit-rtx-6000-pro-1"
	MachineRTXP6000X2    Machine = "lit-rtx-6000-pro-2"
	MachineRTXP6000X4    Machine = "lit-rtx-6000-pro-4"
	MachineRTXP6000X8    Machine = "lit-rtx-6000-pro-8"
	MachineA10G          Machine = "lit-a10g-1"
	MachineA100          Machine = "lit-a100-1"
	MachineA100X2        Machine = "lit-a100-2"
	MachineA100X4        Machine = "lit-a100-4"
	MachineA100X8        Machine = "lit-a100-8"
	MachineA10040GB      Machine = "lit-a100-40gb-1"
	MachineA10040GBX2    Machine = "lit-a100-40gb-2"
	MachineA10040GBX4    Machine = "lit-a100-40gb-4"
	MachineA10040GBX8    Machine = "lit-a100-40gb-8"
	MachineA10080GB      Machine = "lit-a100-80gb-1"
	MachineA10080GBX2    Machine = "lit-a100-80gb-2"
	MachineA10080GBX4    Machine = "lit-a100-80gb-4"
	MachineA10080GBX8    Machine = "lit-a100-80gb-8"
	MachineH100          Machine = "lit-h100-1"
	MachineH100X2        Machine = "lit-h100-2"
	MachineH100X4        Machine = "lit-h100-4"
	MachineH100X8        Machine = "lit-h100-8"
	MachineH200          Machine = "lit-h200x-1"
	MachineH200X8        Machine = "lit-h200x-8"
	MachineB200X8        Machine = "lit-b200x-8"
)

var knownMachineNames = map[string]Machine{
	"cpu_small":       MachineCPUSmall,
	"cpu":             MachineCPU,
	"cpu_x_2":         MachineCPUX2,
	"cpu_x_4":         MachineCPUX4,
	"cpu_x_8":         MachineCPUX8,
	"cpu_x_16":        MachineCPUX16,
	"data_prep":       MachineDataPrep,
	"data_prep_max":   MachineDataPrepMax,
	"data_prep_ultra": MachineDataPrepUltra,
	"t4_small":        MachineT4Small,
	"t4":              MachineT4,
	"t4_x_2":          MachineT4X2,
	"t4_x_4":          MachineT4X4,
	"t4_x_8":          MachineT4X8,
	"l4":              MachineL4,
	"l4_x_2":          MachineL4X2,
	"l4_x_4":          MachineL4X4,
	"l4_x_8":          MachineL4X8,
	"l40s":            MachineL40S,
	"l40s_x_2":        MachineL40SX2,
	"l40s_x_4":        MachineL40SX4,
	"l40s_x_8":        MachineL40SX8,
	"rtxp_6000":       MachineRTXP6000,
	"rtxp_6000_x_2":   MachineRTXP6000X2,
	"rtxp_6000_x_4":   MachineRTXP6000X4,
	"rtxp_6000_x_8":   MachineRTXP6000X8,
	"a10g":            MachineA10G,
	"a100":            MachineA100,
	"a100_x_2":        MachineA100X2,
	"a100_x_4":        MachineA100X4,
	"a100_x_8":        MachineA100X8,
	"a100_40gb":       MachineA10040GB,
	"a100_40gb_x_2":   MachineA10040GBX2,
	"a100_40gb_x_4":   MachineA10040GBX4,
	"a100_40gb_x_8":   MachineA10040GBX8,
	"a100_80gb":       MachineA10080GB,
	"a100_80gb_x_2":   MachineA10080GBX2,
	"a100_80gb_x_4":   MachineA10080GBX4,
	"a100_80gb_x_8":   MachineA10080GBX8,
	"h100":            MachineH100,
	"h100_x_2":        MachineH100X2,
	"h100_x_4":        MachineH100X4,
	"h100_x_8":        MachineH100X8,
	"h200":            MachineH200,
	"h200_x_8":        MachineH200X8,
	"b200_x_8":        MachineB200X8,
}

var knownMachineSlugs = map[string]Machine{
	"cpu-2":                       MachineCPUX2,
	"cpu-4":                       MachineCPUX4,
	"cpu-8":                       MachineCPUX8,
	"cpu-16":                      MachineCPUX16,
	"cpu x 2":                     MachineCPUX2,
	"cpu x 4":                     MachineCPUX4,
	"cpu x 8":                     MachineCPUX8,
	"cpu x 16":                    MachineCPUX16,
	"data-prep-mid":               MachineDataPrep,
	"data-prep-max-large":         MachineDataPrepMax,
	"data-prep-ultra-extra-large": MachineDataPrepUltra,
	"lit-t4-1-small":              MachineT4Small,
	"lit-t4-1":                    MachineT4,
	"lit-t4-2":                    MachineT4X2,
	"lit-t4-4":                    MachineT4X4,
	"lit-t4-8":                    MachineT4X8,
	"lit-l4-1":                    MachineL4,
	"lit-l4-2":                    MachineL4X2,
	"lit-l4-4":                    MachineL4X4,
	"lit-l4-8":                    MachineL4X8,
	"lit-l40s-1":                  MachineL40S,
	"lit-l40s-2":                  MachineL40SX2,
	"lit-l40s-4":                  MachineL40SX4,
	"lit-l40s-8":                  MachineL40SX8,
	"lit-rtx-6000-pro-1":          MachineRTXP6000,
	"lit-rtx-6000-pro-2":          MachineRTXP6000X2,
	"lit-rtx-6000-pro-4":          MachineRTXP6000X4,
	"lit-rtx-6000-pro-8":          MachineRTXP6000X8,
	"a10g x 1":                    MachineA10G,
	"lit-a10g-1":                  MachineA10G,
	"a100 x 1":                    MachineA100,
	"a100 x 2":                    MachineA100X2,
	"a100 x 4":                    MachineA100X4,
	"a100 x 8":                    MachineA100X8,
	"lit-a100-1":                  MachineA100,
	"lit-a100-2":                  MachineA100X2,
	"lit-a100-4":                  MachineA100X4,
	"lit-a100-8":                  MachineA100X8,
	"lit-a100-40gb-1":             MachineA10040GB,
	"lit-a100-40gb-2":             MachineA10040GBX2,
	"lit-a100-40gb-4":             MachineA10040GBX4,
	"lit-a100-40gb-8":             MachineA10040GBX8,
	"lit-a100-80gb-1":             MachineA10080GB,
	"lit-a100-80gb-2":             MachineA10080GBX2,
	"lit-a100-80gb-4":             MachineA10080GBX4,
	"lit-a100-80gb-8":             MachineA10080GBX8,
	"h100 x 1":                    MachineH100,
	"h100 x 2":                    MachineH100X2,
	"h100 x 4":                    MachineH100X4,
	"h100 x 8":                    MachineH100X8,
	"lit-h100-1":                  MachineH100,
	"lit-h100-2":                  MachineH100X2,
	"lit-h100-4":                  MachineH100X4,
	"lit-h100-8":                  MachineH100X8,
	"lit-h200x-1":                 MachineH200,
	"lit-h200x-8":                 MachineH200X8,
	"lit-b200x-8":                 MachineB200X8,
}

// machineFromString resolves known machine identifiers and returns an ad-hoc value for unknown identifiers.
func machineFromString(machine string, additional ...string) Machine {
	for _, value := range append([]string{machine}, additional...) {
		if value == "" {
			continue
		}
		if known, ok := knownMachineNames[strings.ToLower(value)]; ok {
			return known
		}
		if known, ok := knownMachineSlugs[strings.ToLower(value)]; ok {
			return known
		}
	}
	return Machine(machine)
}

func machineFromAccelerator(accelerator *models.V1ClusterAccelerator) Machine {
	count := int64(0)
	if accelerator.Resources != nil {
		count = firstNonZero(accelerator.Resources.Gpu, accelerator.Resources.CPU)
	}
	return machineFromString(
		accelerator.SlugMultiCloud,
		accelerator.Slug,
		accelerator.InstanceID,
		accelerator.SecondaryInstanceID,
		machineSlugForFamily(accelerator.Family, count),
		accelerator.DisplayName,
	)
}

func machineSlugForFamily(family string, count int64) string {
	normalized := strings.ToUpper(strings.ReplaceAll(family, " ", "_"))
	switch normalized {
	case "CPU":
		switch count {
		case 2:
			return "cpu-2"
		case 4:
			return "cpu-4"
		case 8:
			return "cpu-8"
		case 16:
			return "cpu-16"
		}
	case "T4", "L4", "L40S", "A100", "H100":
		switch count {
		case 1:
			return fmt.Sprintf("lit-%s-1", strings.ToLower(normalized))
		case 2, 4, 8:
			return fmt.Sprintf("lit-%s-%d", strings.ToLower(normalized), count)
		}
	case "RTX_PRO":
		switch count {
		case 1:
			return "lit-rtx-6000-pro-1"
		case 2:
			return "lit-rtx-6000-pro-2"
		case 4:
			return "lit-rtx-6000-pro-4"
		case 8:
			return "lit-rtx-6000-pro-8"
		}
	case "A10G":
		return "lit-a10g-1"
	case "H200":
		if count == 8 {
			return "lit-h200x-8"
		}
		return "lit-h200x-1"
	case "B200":
		if count == 8 {
			return "lit-b200x-8"
		}
	}
	return ""
}

func matchesMachine(accelerator *models.V1ClusterAccelerator, machine string) bool {
	if machine == "" {
		return true
	}
	needle := strings.ToLower(machine)
	for _, value := range []string{
		accelerator.InstanceID,
		accelerator.Slug,
		accelerator.SlugMultiCloud,
		accelerator.Family,
		accelerator.DisplayName,
		string(machineFromAccelerator(accelerator)),
	} {
		if strings.Contains(strings.ToLower(value), needle) {
			return true
		}
	}
	return false
}

func matchesProvider(accelerator *models.V1ClusterAccelerator, provider string) bool {
	if provider == "" {
		return true
	}
	return accelerator.Provider != nil && string(*accelerator.Provider) == provider
}

func firstNonZero(values ...int64) int64 {
	for _, value := range values {
		if value != 0 {
			return value
		}
	}
	return 0
}

func normalizeCloudProvider(cloud string) string {
	return strings.ToUpper(strings.ReplaceAll(cloud, "-", "_"))
}

func isCloudProvider(cloud string) bool {
	switch normalizeCloudProvider(cloud) {
	case string(models.V1CloudProviderAWS),
		string(models.V1CloudProviderGCP),
		string(models.V1CloudProviderVULTR),
		string(models.V1CloudProviderLAMBDALABS),
		string(models.V1CloudProviderSLURM),
		string(models.V1CloudProviderDGX),
		string(models.V1CloudProviderVOLTAGEPARK),
		string(models.V1CloudProviderNEBIUS),
		string(models.V1CloudProviderCLOUDFLARE),
		string(models.V1CloudProviderLIGHTNING),
		string(models.V1CloudProviderLIGHTNINGAGGREGATE),
		string(models.V1CloudProviderKUBERNETES),
		string(models.V1CloudProviderMACHINE),
		string(models.V1CloudProviderLIGHTNINGELASTICCLUSTERAGGREGATE),
		string(models.V1CloudProviderCUDO),
		string(models.V1CloudProviderMITHRIL),
		string(models.V1CloudProviderTHUNDERCAT),
		string(models.V1CloudProviderTENSORDOCK),
		string(models.V1CloudProviderAZURE):
		return true
	default:
		return false
	}
}
