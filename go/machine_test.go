package lit_test

import (
	"fmt"
	"testing"

	lit "github.com/gridai/lightning-sdk/go"
	"github.com/stretchr/testify/assert"
)

func TestMachineConstantsUsePythonMultiCloudSlugs(t *testing.T) {
	cases := map[lit.Machine]string{
		lit.MachineCPUSmall:      "cpu-2",
		lit.MachineCPU:           "cpu-4",
		lit.MachineDataPrep:      "data-prep-mid",
		lit.MachineT4Small:       "lit-t4-1-small",
		lit.MachineL4:            "lit-l4-1",
		lit.MachineL4X8:          "lit-l4-8",
		lit.MachineL40SX4:        "lit-l40s-4",
		lit.MachineRTXP6000X2:    "lit-rtx-6000-pro-2",
		lit.MachineA100:          "lit-a100-1",
		lit.MachineA10040GBX8:    "lit-a100-40gb-8",
		lit.MachineA10080GBX4:    "lit-a100-80gb-4",
		lit.MachineH100X8:        "lit-h100-8",
		lit.MachineH200:          "lit-h200x-1",
		lit.MachineH200X8:        "lit-h200x-8",
		lit.MachineB200X8:        "lit-b200x-8",
		lit.MachineDataPrepUltra: "data-prep-ultra-extra-large",
	}

	for machine, want := range cases {
		if got := string(machine); got != want {
			assert.Fail(t, fmt.Sprintf("machine slug = %q, want %q", got, want))
		}
	}
}
