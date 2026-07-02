package lit

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/client/jobs_service"
	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/models"
	"github.com/gridai/lightning-sdk/go/internal/sdkclient"
)

// MMT represents a Lightning multi-machine job.
type MMT struct {
	id          string
	name        string
	teamspaceID string
	teamspace   string
	ownerName   string
	status      string
	numMachines int64
	machine     string
	command     string
	image       string
	studioID    string
	totalCost   float32
}

// MachineDict is the JSON-friendly public representation of one MMT machine.
type MachineDict struct {
	Name    string `json:"name"`
	Status  string `json:"status"`
	Machine string `json:"machine"`
}

// MMTDict is the JSON-friendly public representation of an MMT.
type MMTDict struct {
	Name      string        `json:"name"`
	Teamspace string        `json:"teamspace"`
	Studio    *string       `json:"studio"`
	Image     *string       `json:"image"`
	Command   string        `json:"command"`
	Status    string        `json:"status"`
	Machine   string        `json:"machine"`
	Machines  []MachineDict `json:"machines"`
	TotalCost float32       `json:"total_cost"`
}

// MMTPathMapping maps a teamspace connection path into an MMT container.
type MMTPathMapping struct {
	ContainerPath  string
	ConnectionName string
	ConnectionPath string
}

type mmtOptions struct {
	id               string
	teamspaceID      string
	teamspaceName    string
	ownerName        string
	studioID         string
	status           string
	numMachines      int64
	machine          string
	command          string
	image            string
	totalCost        float32
	env              map[string]string
	cloud            string
	interruptible    bool
	imageCredentials string
	cloudAccountAuth bool
	entrypoint       *string
	pathMappings     []MMTPathMapping
	artifactsSource  string
	artifactsDest    string
	maxRuntime       int
}

type mmtWaitOptions struct {
	interval      time.Duration
	timeout       time.Duration
	stopOnTimeout bool
}

// MMTOptions configures MMT lookup and creation.
type MMTOptions struct {
	ID                   string
	Teamspace            *Teamspace
	Studio               *Studio
	Status               string
	NumMachines          int64
	Machine              Machine
	Command              string
	Image                string
	TotalCost            float32
	Env                  map[string]string
	Cloud                string
	Interruptible        *bool
	ImageCredentials     string
	CloudAccountAuth     bool
	Entrypoint           string
	PathMappings         []MMTPathMapping
	ArtifactsSource      string
	ArtifactsDestination string
	MaxRuntime           int
}

// MMTWaitOptions configures polling behavior while waiting for an MMT.
type MMTWaitOptions struct {
	Interval      time.Duration
	Timeout       time.Duration
	StopOnTimeout bool
}

// ID returns the MMT ID.
func (m *MMT) ID() string {
	if m == nil {
		return ""
	}
	return m.id
}

// TeamspaceID returns the owning teamspace ID.
func (m *MMT) TeamspaceID() string {
	if m == nil {
		return ""
	}
	return m.teamspaceID
}

// StudioID returns the source studio ID when the MMT uses a studio.
func (m *MMT) StudioID() string {
	if m == nil {
		return ""
	}
	return m.studioID
}

// Name returns the MMT name.
func (m *MMT) Name() string {
	if m == nil {
		return ""
	}
	return m.name
}

// Teamspace returns the owning teamspace name.
func (m *MMT) Teamspace() string {
	if m == nil {
		return ""
	}
	return m.teamspace
}

// OwnerName returns the owning user or organization name.
func (m *MMT) OwnerName() string {
	if m == nil {
		return ""
	}
	return m.ownerName
}

// Status returns the latest known MMT state.
func (m *MMT) Status() string {
	if m == nil {
		return ""
	}
	return m.status
}

// NumMachines returns the requested number of machines.
func (m *MMT) NumMachines() int64 {
	if m == nil {
		return 0
	}
	return m.numMachines
}

// Machine returns the configured machine.
func (m *MMT) Machine() string {
	if m == nil {
		return ""
	}
	return m.machine
}

// Command returns the command run by the MMT.
func (m *MMT) Command() string {
	if m == nil {
		return ""
	}
	return m.command
}

// Image returns the image used by the MMT.
func (m *MMT) Image() string {
	if m == nil {
		return ""
	}
	return m.image
}

// TotalCost returns the latest known total cost.
func (m *MMT) TotalCost() float32 {
	if m == nil {
		return 0
	}
	return m.totalCost
}

// GetMMT returns an existing MMT by name or ID.
func GetMMT(name string, opts ...MMTOptions) (*MMT, error) {
	resolved := applyMMTOptions(opts...)
	if name == "" && resolved.id == "" {
		return nil, errors.New("mmt requires name or ID")
	}
	if resolved.id != "" {
		return &MMT{
			id:          resolved.id,
			name:        name,
			teamspaceID: resolved.teamspaceID,
			teamspace:   resolved.teamspaceName,
			ownerName:   resolved.ownerName,
			status:      resolved.status,
			numMachines: resolved.numMachines,
			machine:     resolved.machine,
			command:     resolved.command,
			image:       resolved.image,
			studioID:    resolved.studioID,
			totalCost:   resolved.totalCost,
		}, nil
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	if resolved.teamspaceID == "" {
		return nil, errors.New("mmt requires teamspace")
	}
	resp, err := api.JobsService.JobsServiceGetMultiMachineJobByName(
		jobs_service.NewJobsServiceGetMultiMachineJobByNameParamsWithContext(context.Background()).
			WithName(name).
			WithProjectID(resolved.teamspaceID),
	)
	if err != nil {
		return nil, err
	}
	return mmtFromModel(resp.Payload, resolved), nil
}

// RunMMT creates and starts a new MMT.
func RunMMT(name string, numMachines int64, machine Machine, command string, opts ...MMTOptions) (*MMT, error) {
	resolved := applyMMTOptions(opts...)
	if name == "" {
		return nil, errors.New("mmt run requires name")
	}
	if numMachines <= 1 {
		return nil, errors.New("mmt run cannot use less than 2 machines")
	}
	if err := validateMMTComputeEnvironment(command, resolved); err != nil {
		return nil, err
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	if resolved.teamspaceID == "" {
		return nil, errors.New("mmt run requires teamspace or studio")
	}
	body := &models.JobsServiceCreateMultiMachineJobBody{
		ClusterID: resolved.cloud,
		Machines:  numMachines,
		Name:      name,
		Spec:      mmtJobSpec(numMachines, string(machine), command, resolved),
	}
	resp, err := api.JobsService.JobsServiceCreateMultiMachineJob(
		jobs_service.NewJobsServiceCreateMultiMachineJobParamsWithContext(context.Background()).WithProjectID(resolved.teamspaceID).WithBody(body),
	)
	if err != nil {
		return nil, err
	}
	return mmtFromModel(resp.Payload, resolved), nil
}

// Stop stops the MMT.
func (m *MMT) Stop() error {
	if m == nil || m.teamspaceID == "" || m.id == "" {
		return errors.New("mmt stop requires teamspace ID and MMT ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	desiredState := models.V1MultiMachineJobStateMultiMachineJobSTATESTOP
	resp, err := api.JobsService.JobsServiceUpdateMultiMachineJob(
		jobs_service.NewJobsServiceUpdateMultiMachineJobParamsWithContext(context.Background()).
			WithProjectID(m.teamspaceID).
			WithID(m.id).
			WithBody(&models.JobsServiceUpdateMultiMachineJobBody{DesiredState: &desiredState}),
	)
	if err != nil {
		return err
	}
	updated := mmtFromModel(resp.Payload, mmtOptions{teamspaceName: m.teamspace, ownerName: m.ownerName})
	if updated != nil {
		*m = *updated
	}
	return nil
}

// Delete deletes the MMT.
func (m *MMT) Delete() error {
	if m == nil || m.teamspaceID == "" || m.id == "" {
		return errors.New("mmt delete requires teamspace ID and MMT ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	_, err = api.JobsService.JobsServiceDeleteMultiMachineJob(
		jobs_service.NewJobsServiceDeleteMultiMachineJobParamsWithContext(context.Background()).
			WithProjectID(m.teamspaceID).
			WithID(m.id),
	)
	return err
}

// Wait polls until the MMT reaches a terminal state.
func (m *MMT) Wait(opts ...MMTWaitOptions) error {
	if m == nil || m.teamspaceID == "" || m.id == "" {
		return errors.New("mmt wait requires teamspace ID and MMT ID")
	}
	resolved := applyMMTWaitOptions(opts...)
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	start := time.Now()
	for {
		resp, err := api.JobsService.JobsServiceGetMultiMachineJob(
			jobs_service.NewJobsServiceGetMultiMachineJobParamsWithContext(context.Background()).
				WithProjectID(m.teamspaceID).
				WithID(m.id),
		)
		if err != nil {
			return err
		}
		updated := mmtFromModel(resp.Payload, mmtOptions{teamspaceName: m.teamspace, ownerName: m.ownerName})
		if updated == nil {
			return fmt.Errorf("get mmt returned empty payload")
		}
		*m = *updated
		if isMMTTerminalStatus(m.status) {
			return nil
		}
		if resolved.timeout > 0 && time.Since(start) > resolved.timeout {
			if resolved.stopOnTimeout {
				_ = m.Stop()
			}
			return fmt.Errorf("mmt didn't finish within the provided timeout")
		}
		time.Sleep(resolved.interval)
	}
}

// Machines lists the jobs backing the MMT.
func (m *MMT) Machines() ([]*Job, error) {
	if m == nil || m.teamspaceID == "" || m.id == "" {
		return nil, errors.New("mmt machines requires teamspace ID and MMT ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	var result []*Job
	var pageToken string
	for {
		params := jobs_service.NewJobsServiceListJobsParamsWithContext(context.Background()).
			WithProjectID(m.teamspaceID).
			WithMultiMachineJobID(&m.id)
		if pageToken != "" {
			params = params.WithPageToken(&pageToken)
		}
		resp, err := api.JobsService.JobsServiceListJobs(params)
		if err != nil {
			return nil, err
		}
		if resp.Payload == nil {
			return nil, fmt.Errorf("list mmt machines returned empty payload")
		}
		for _, model := range resp.Payload.Jobs {
			if model == nil {
				continue
			}
			result = append(result, m.jobFromModel(model))
		}
		if resp.Payload.NextPageToken == "" {
			return result, nil
		}
		pageToken = resp.Payload.NextPageToken
	}
}

// Logs returns logs from the first machine in the MMT.
func (m *MMT) Logs() (string, error) {
	machines, err := m.Machines()
	if err != nil {
		return "", err
	}
	if len(machines) == 0 {
		return "", errors.New("mmt logs require at least one machine")
	}
	return machines[0].Logs()
}

// Dict returns a JSON-friendly public representation of the MMT.
func (m *MMT) Dict() (MMTDict, error) {
	if m == nil {
		return MMTDict{}, nil
	}
	machines, err := m.Machines()
	if err != nil {
		return MMTDict{}, err
	}
	machineDicts := make([]MachineDict, 0, len(machines))
	for _, machine := range machines {
		if machine == nil {
			continue
		}
		machineDicts = append(machineDicts, MachineDict{
			Name:    machine.Name(),
			Status:  machine.Status(),
			Machine: machine.Machine(),
		})
	}
	var studioName *string
	if m.studioID != "" {
		studioName = &m.studioID
	}
	var image *string
	if m.image != "" {
		image = &m.image
	}
	return MMTDict{
		Name:      m.name,
		Teamspace: ownerTeamspace(m.ownerName, m.teamspace),
		Studio:    studioName,
		Image:     image,
		Command:   m.command,
		Status:    m.status,
		Machine:   m.machine,
		Machines:  machineDicts,
		TotalCost: m.totalCost,
	}, nil
}

// JSON returns an indented JSON representation of the MMT.
func (m *MMT) JSON() (string, error) {
	dict, err := m.Dict()
	if err != nil {
		return "", err
	}
	body, err := json.MarshalIndent(dict, "", "    ")
	if err != nil {
		return "", err
	}
	return string(body), nil
}

// ArtifactPath returns the artifact path for the MMT when available.
func (m *MMT) ArtifactPath() string {
	return ""
}

// SnapshotPath returns the snapshot path for the MMT when available.
func (m *MMT) SnapshotPath() string {
	return ""
}

// SharePath returns the share path for the MMT when available.
func (m *MMT) SharePath() string {
	return ""
}

// Link returns the Lightning web URL for the MMT.
func (m *MMT) Link() string {
	if m == nil || m.ownerName == "" || m.teamspace == "" || m.name == "" {
		return ""
	}
	return fmt.Sprintf("https://lightning.ai/%s/%s/jobs/%s?app_id=mmt", m.ownerName, m.teamspace, m.name)
}

func applyMMTOptions(opts ...MMTOptions) mmtOptions {
	var resolved mmtOptions
	if len(opts) > 0 {
		resolved.id = opts[0].ID
		if opts[0].Teamspace != nil {
			resolved.teamspaceID = opts[0].Teamspace.ID()
			resolved.teamspaceName = opts[0].Teamspace.Name()
			if resolved.cloud == "" {
				resolved.cloud = opts[0].Teamspace.DefaultCloudAccount()
			}
			if owner := opts[0].Teamspace.Owner(); owner != nil {
				resolved.ownerName = owner.Name()
			}
		}
		if opts[0].Studio != nil {
			resolved.studioID = opts[0].Studio.ID()
			if resolved.teamspaceID == "" {
				resolved.teamspaceID = opts[0].Studio.TeamspaceID()
				resolved.teamspaceName = opts[0].Studio.Teamspace()
				resolved.ownerName = opts[0].Studio.OwnerName()
			}
		}
		resolved.status = opts[0].Status
		resolved.numMachines = opts[0].NumMachines
		resolved.machine = string(opts[0].Machine)
		resolved.command = opts[0].Command
		resolved.image = opts[0].Image
		resolved.totalCost = opts[0].TotalCost
		resolved.env = opts[0].Env
		resolved.cloud = opts[0].Cloud
		if opts[0].Interruptible != nil {
			resolved.interruptible = *opts[0].Interruptible
		}
		resolved.imageCredentials = opts[0].ImageCredentials
		resolved.cloudAccountAuth = opts[0].CloudAccountAuth
		if opts[0].Entrypoint != "" {
			resolved.entrypoint = &opts[0].Entrypoint
		}
		resolved.pathMappings = opts[0].PathMappings
		resolved.artifactsSource = opts[0].ArtifactsSource
		resolved.artifactsDest = opts[0].ArtifactsDestination
		resolved.maxRuntime = opts[0].MaxRuntime
	}
	return resolved
}

func applyMMTWaitOptions(opts ...MMTWaitOptions) mmtWaitOptions {
	resolved := mmtWaitOptions{interval: 5 * time.Second}
	if len(opts) > 0 {
		resolved.interval = opts[0].Interval
		resolved.timeout = opts[0].Timeout
		resolved.stopOnTimeout = opts[0].StopOnTimeout
		if resolved.interval == 0 {
			resolved.interval = 5 * time.Second
		}
	}
	if resolved.interval < 0 {
		resolved.interval = 0
	}
	return resolved
}

func validateMMTComputeEnvironment(command string, opts mmtOptions) error {
	if opts.studioID != "" {
		if opts.image != "" {
			return errors.New("image and studio are mutually exclusive as both define the environment to run the job in")
		}
		if command == "" {
			return errors.New("command is required when using a studio")
		}
		if opts.artifactsSource != "" || opts.artifactsDest != "" {
			return errors.New("artifacts are only supported when using a custom image")
		}
		return nil
	}
	if opts.image == "" {
		return errors.New("either image or studio must be provided")
	}
	if err := validateArtifacts(opts.artifactsSource, opts.artifactsDest); err != nil {
		return err
	}
	return nil
}

func mmtFromModel(model *models.V1MultiMachineJob, opts mmtOptions) *MMT {
	if model == nil {
		return nil
	}
	result := &MMT{
		id:          model.ID,
		name:        model.Name,
		teamspaceID: model.ProjectID,
		teamspace:   opts.teamspaceName,
		ownerName:   opts.ownerName,
		numMachines: model.Machines,
		studioID:    model.CloudspaceID,
		totalCost:   model.TotalCost,
	}
	if model.State != nil {
		result.status = string(*model.State)
	}
	if model.Spec != nil {
		result.machine = model.Spec.InstanceName
		result.command = model.Spec.Command
		result.image = model.Spec.Image
		if result.studioID == "" {
			result.studioID = model.Spec.CloudspaceID
		}
	}
	return result
}

func isMMTTerminalStatus(status string) bool {
	switch strings.ToLower(status) {
	case "completed", "stopped", "failed", "multimachinejob_state_completed", "multimachinejob_state_stopped", "multimachinejob_state_failed":
		return true
	default:
		return false
	}
}

func (m *MMT) jobFromModel(model *models.V1Job) *Job {
	if model == nil {
		return nil
	}
	opts := jobOptions{
		id:            model.ID,
		teamspaceID:   model.ProjectID,
		teamspaceName: m.teamspace,
		ownerName:     m.ownerName,
		mmtID:         model.MultiMachineJobID,
		status:        model.State,
		publicIP:      model.PublicIPAddress,
		totalCost:     model.TotalCost,
	}
	if model.Spec != nil {
		opts.studioID = model.Spec.CloudspaceID
		opts.machine = model.Spec.InstanceName
		opts.command = model.Spec.Command
		opts.image = model.Spec.Image
	}
	return jobFromModel(model, opts)
}

func mmtJobSpec(numMachines int64, machine, command string, opts mmtOptions) *models.V1JobSpec {
	return &models.V1JobSpec{
		CloudspaceID:                opts.studioID,
		ClusterID:                   opts.cloud,
		Command:                     command,
		Entrypoint:                  resolveEntrypoint(command, opts.entrypoint, opts.image),
		Env:                         envVars(opts.env),
		Image:                       opts.image,
		ImageClusterCredentials:     opts.cloudAccountAuth,
		ImageSecretRef:              opts.imageCredentials,
		InstanceName:                machine,
		PathMappings:                mmtPathMappings(opts),
		Quantity:                    numMachines,
		RequestedRunDurationSeconds: maxRuntime(opts.maxRuntime),
		Spot:                        opts.interruptible,
	}
}

func mmtPathMappings(opts mmtOptions) []*models.V1PathMapping {
	if len(opts.pathMappings) == 0 && opts.artifactsSource == "" {
		return nil
	}
	result := make([]*models.V1PathMapping, 0, len(opts.pathMappings)+1)
	for _, mapping := range opts.pathMappings {
		result = append(result, &models.V1PathMapping{
			ConnectionName: mapping.ConnectionName,
			ConnectionPath: mapping.ConnectionPath,
			ContainerPath:  mapping.ContainerPath,
		})
	}
	if opts.artifactsSource != "" {
		connectionName, connectionPath := artifactConnection(opts.artifactsDest)
		result = append(result, &models.V1PathMapping{
			ConnectionName: connectionName,
			ConnectionPath: connectionPath,
			ContainerPath:  opts.artifactsSource,
		})
	}
	return result
}
