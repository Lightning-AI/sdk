package lit

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"path"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/client/jobs_service"
	"github.com/gridai/lightning-sdk/go/internal/lightningcloud/openapi/generated/models"
	"github.com/gridai/lightning-sdk/go/internal/sdkclient"
)

var datetimePrefix = regexp.MustCompile(`(?m)^\[.*?\] `)

// Job represents a Lightning single-machine job.
type Job struct {
	id          string
	name        string
	teamspaceID string
	teamspace   string
	ownerName   string
	status      string
	machine     string
	command     string
	image       string
	studioID    string
	mmtID       string
	publicIP    string
	totalCost   float32

	artifactsSource      string
	artifactsDestination string
}

// JobDict is the JSON-friendly public representation of a job.
type JobDict struct {
	Name      string  `json:"name"`
	Teamspace string  `json:"teamspace"`
	Studio    *string `json:"studio"`
	Image     *string `json:"image"`
	Command   string  `json:"command"`
	Status    string  `json:"status"`
	Machine   string  `json:"machine"`
	TotalCost float32 `json:"total_cost"`
}

// JobPathMapping maps a teamspace connection path into a job container.
type JobPathMapping struct {
	ContainerPath  string
	ConnectionName string
	ConnectionPath string
}

// ScratchDisk configures a scratch disk mount for a studio-backed job.
type ScratchDisk struct {
	Path   string
	SizeGB int
}

type jobOptions struct {
	id               string
	teamspaceID      string
	teamspaceName    string
	ownerName        string
	studioID         string
	mmtID            string
	status           string
	machine          string
	command          string
	image            string
	publicIP         string
	totalCost        float32
	env              map[string]string
	cloud            string
	interruptible    bool
	imageCredentials string
	cloudAccountAuth bool
	entrypoint       *string
	pathMappings     []JobPathMapping
	artifactsSource  string
	artifactsDest    string
	maxRuntime       int
	scratchDisks     []ScratchDisk
}

type jobWaitOptions struct {
	interval      time.Duration
	timeout       time.Duration
	stopOnTimeout bool
}

// JobOptions configures job lookup and creation.
type JobOptions struct {
	ID                   string
	Teamspace            *Teamspace
	Studio               *Studio
	MMT                  *MMT
	Status               string
	Machine              Machine
	Command              string
	Image                string
	PublicIP             string
	TotalCost            float32
	Env                  map[string]string
	Cloud                string
	Interruptible        *bool
	ImageCredentials     string
	CloudAccountAuth     bool
	Entrypoint           string
	PathMappings         []JobPathMapping
	ArtifactsSource      string
	ArtifactsDestination string
	MaxRuntime           int
	ScratchDisks         []ScratchDisk
}

// JobWaitOptions configures polling behavior while waiting for a job.
type JobWaitOptions struct {
	Interval      time.Duration
	Timeout       time.Duration
	StopOnTimeout bool
}

// ID returns the job ID.
func (j *Job) ID() string {
	if j == nil {
		return ""
	}
	return j.id
}

// TeamspaceID returns the owning teamspace ID.
func (j *Job) TeamspaceID() string {
	if j == nil {
		return ""
	}
	return j.teamspaceID
}

// StudioID returns the source studio ID when the job uses a studio.
func (j *Job) StudioID() string {
	if j == nil {
		return ""
	}
	return j.studioID
}

// MMTID returns the parent multi-machine job ID when present.
func (j *Job) MMTID() string {
	if j == nil {
		return ""
	}
	return j.mmtID
}

// Name returns the job name.
func (j *Job) Name() string {
	if j == nil {
		return ""
	}
	return j.name
}

// Teamspace returns the owning teamspace name.
func (j *Job) Teamspace() string {
	if j == nil {
		return ""
	}
	return j.teamspace
}

// OwnerName returns the owning user or organization name.
func (j *Job) OwnerName() string {
	if j == nil {
		return ""
	}
	return j.ownerName
}

// Status returns the latest known job state.
func (j *Job) Status() string {
	if j == nil {
		return ""
	}
	return j.status
}

// Machine returns the configured machine.
func (j *Job) Machine() string {
	if j == nil {
		return ""
	}
	return j.machine
}

// Command returns the command run by the job.
func (j *Job) Command() string {
	if j == nil {
		return ""
	}
	return j.command
}

// Image returns the image used by the job.
func (j *Job) Image() string {
	if j == nil {
		return ""
	}
	return j.image
}

// PublicIP returns the latest known public IP.
func (j *Job) PublicIP() string {
	if j == nil {
		return ""
	}
	return j.publicIP
}

// TotalCost returns the latest known total cost.
func (j *Job) TotalCost() float32 {
	if j == nil {
		return 0
	}
	return j.totalCost
}

// ArtifactsSource returns the local artifacts source path.
func (j *Job) ArtifactsSource() string {
	if j == nil {
		return ""
	}
	return j.artifactsSource
}

// ArtifactsDestination returns the remote artifacts destination path.
func (j *Job) ArtifactsDestination() string {
	if j == nil {
		return ""
	}
	return j.artifactsDestination
}

// GetJob returns an existing job by name or ID.
func GetJob(name string, opts ...JobOptions) (*Job, error) {
	resolved := applyJobOptions(opts...)
	if name == "" && resolved.id == "" {
		return nil, errors.New("job requires name or ID")
	}
	if resolved.id != "" {
		return &Job{
			id:                   resolved.id,
			name:                 name,
			teamspaceID:          resolved.teamspaceID,
			teamspace:            resolved.teamspaceName,
			ownerName:            resolved.ownerName,
			status:               resolved.status,
			machine:              resolved.machine,
			command:              resolved.command,
			image:                resolved.image,
			studioID:             resolved.studioID,
			mmtID:                resolved.mmtID,
			publicIP:             resolved.publicIP,
			totalCost:            resolved.totalCost,
			artifactsSource:      resolved.artifactsSource,
			artifactsDestination: resolved.artifactsDest,
		}, nil
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	params := jobs_service.NewJobsServiceGetJobByName2ParamsWithContext(context.Background()).WithJobName(name)
	if resolved.teamspaceID != "" {
		params = params.WithProjectID(&resolved.teamspaceID)
	} else {
		return nil, errors.New("job requires teamspace")
	}
	resp, err := api.JobsService.JobsServiceGetJobByName2(params)
	if err != nil {
		return nil, err
	}
	return jobFromModel(resp.Payload, resolved), nil
}

// RunJob creates and starts a new job.
func RunJob(name string, machine Machine, command string, opts ...JobOptions) (*Job, error) {
	resolved := applyJobOptions(opts...)
	if name == "" {
		return nil, errors.New("job run requires name")
	}
	if err := validateJobComputeEnvironment(command, resolved); err != nil {
		return nil, err
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	if resolved.teamspaceID == "" {
		return nil, errors.New("job run requires teamspace or studio")
	}
	body := &models.JobsServiceCreateJobBody{
		Name: name,
		Spec: jobSpec(string(machine), command, resolved),
	}
	resp, err := api.JobsService.JobsServiceCreateJob(
		jobs_service.NewJobsServiceCreateJobParamsWithContext(context.Background()).WithProjectID(resolved.teamspaceID).WithBody(body),
	)
	if err != nil {
		return nil, err
	}
	return jobFromModel(resp.Payload, resolved), nil
}

// Stop stops the job.
func (j *Job) Stop() error {
	if j == nil || j.teamspaceID == "" || j.id == "" {
		return errors.New("job stop requires teamspace ID and job ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	resp, err := api.JobsService.JobsServiceUpdateJob(
		jobs_service.NewJobsServiceUpdateJobParamsWithContext(context.Background()).
			WithProjectID(j.teamspaceID).
			WithID(j.id).
			WithBody(&models.JobsServiceUpdateJobBody{State: "stopped"}),
	)
	if err != nil {
		return err
	}
	updated := jobFromModel(resp.Payload, jobOptions{teamspaceName: j.teamspace, ownerName: j.ownerName})
	if updated != nil {
		if updated.studioID == "" {
			updated.studioID = j.studioID
		}
		*j = *updated
	}
	return nil
}

// Delete deletes the job.
func (j *Job) Delete() error {
	if j == nil || j.teamspaceID == "" || j.id == "" {
		return errors.New("job delete requires teamspace ID and job ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	params := jobs_service.NewJobsServiceDeleteJobParamsWithContext(context.Background()).
		WithProjectID(j.teamspaceID).
		WithID(j.id)
	if j.studioID != "" {
		params = params.WithCloudspaceID(&j.studioID)
	}
	_, err = api.JobsService.JobsServiceDeleteJob(params)
	return err
}

// Wait polls until the job reaches a terminal state.
func (j *Job) Wait(opts ...JobWaitOptions) error {
	if j == nil || j.teamspaceID == "" || j.id == "" {
		return errors.New("job wait requires teamspace ID and job ID")
	}
	resolved := applyJobWaitOptions(opts...)
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	start := time.Now()
	for {
		resp, err := api.JobsService.JobsServiceGetJob(
			jobs_service.NewJobsServiceGetJobParamsWithContext(context.Background()).
				WithProjectID(j.teamspaceID).
				WithID(j.id),
		)
		if err != nil {
			return err
		}
		updated := jobFromModel(resp.Payload, jobOptions{teamspaceName: j.teamspace, ownerName: j.ownerName})
		if updated == nil {
			return fmt.Errorf("get job returned empty payload")
		}
		if updated.studioID == "" {
			updated.studioID = j.studioID
		}
		*j = *updated
		if isJobTerminalStatus(j.status) {
			return nil
		}
		if resolved.timeout > 0 && time.Since(start) > resolved.timeout {
			if resolved.stopOnTimeout {
				_ = j.Stop()
			}
			return fmt.Errorf("job didn't finish within the provided timeout")
		}
		time.Sleep(resolved.interval)
	}
}

// Logs downloads and returns the job logs.
func (j *Job) Logs() (string, error) {
	if j == nil || j.teamspaceID == "" || j.id == "" {
		return "", errors.New("job logs requires teamspace ID and job ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return "", err
	}
	resp, err := api.JobsService.JobsServiceDownloadJobLogs(
		jobs_service.NewJobsServiceDownloadJobLogsParamsWithContext(context.Background()).
			WithProjectID(j.teamspaceID).
			WithID(j.id),
	)
	if err != nil {
		return "", err
	}
	if resp.Payload == nil || resp.Payload.URL == "" {
		return "", fmt.Errorf("download job logs returned empty URL")
	}
	logResp, err := http.Get(resp.Payload.URL)
	if err != nil {
		return "", err
	}
	defer logResp.Body.Close()
	if logResp.StatusCode < 200 || logResp.StatusCode >= 300 {
		return "", fmt.Errorf("download job logs returned status %d", logResp.StatusCode)
	}
	body, err := io.ReadAll(logResp.Body)
	if err != nil {
		return "", err
	}
	return datetimePrefix.ReplaceAllString(string(body), ""), nil
}

// Dict returns a JSON-friendly public representation of the job.
func (j *Job) Dict() JobDict {
	if j == nil {
		return JobDict{}
	}
	var studioName *string
	if j.studioID != "" {
		studioName = &j.studioID
	}
	var image *string
	if j.image != "" {
		image = &j.image
	}
	return JobDict{
		Name:      j.name,
		Teamspace: ownerTeamspace(j.ownerName, j.teamspace),
		Studio:    studioName,
		Image:     image,
		Command:   j.command,
		Status:    j.status,
		Machine:   j.machine,
		TotalCost: j.totalCost,
	}
}

// JSON returns an indented JSON representation of the job.
func (j *Job) JSON() (string, error) {
	body, err := json.MarshalIndent(j.Dict(), "", "    ")
	if err != nil {
		return "", err
	}
	return string(body), nil
}

// Link returns the Lightning web URL for the job.
func (j *Job) Link() string {
	if j == nil {
		return ""
	}
	if j.image != "" && j.mmtID == "" {
		base := jobLink(j.ownerName, j.teamspace, j.name)
		if base == "" {
			return ""
		}
		return base + "?app_id=jobs"
	}
	return jobLink(j.ownerName, j.teamspace, j.name)
}

// ArtifactPath returns the teamspace artifact path for the job.
func (j *Job) ArtifactPath() string {
	if j == nil {
		return ""
	}
	if j.image != "" {
		return artifactDestinationPath(j.artifactsDestination)
	}
	if j.name == "" {
		return ""
	}
	return fmt.Sprintf("/teamspace/jobs/%s/artifacts", j.name)
}

// SnapshotPath returns the teamspace snapshot path for the job.
func (j *Job) SnapshotPath() string {
	if j == nil || j.name == "" || j.image != "" {
		return ""
	}
	return fmt.Sprintf("/teamspace/jobs/%s/snapshot", j.name)
}

// SharePath returns the share path for the job when available.
func (j *Job) SharePath() string {
	return ""
}

func jobLink(ownerName, teamspaceName, jobName string) string {
	if ownerName == "" || teamspaceName == "" || jobName == "" {
		return ""
	}
	return fmt.Sprintf("https://lightning.ai/%s/%s/jobs/%s", ownerName, teamspaceName, jobName)
}

func applyJobOptions(opts ...JobOptions) jobOptions {
	var resolved jobOptions
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
		if opts[0].MMT != nil {
			resolved.mmtID = opts[0].MMT.ID()
			if resolved.teamspaceID == "" {
				resolved.teamspaceID = opts[0].MMT.TeamspaceID()
				resolved.teamspaceName = opts[0].MMT.Teamspace()
				resolved.ownerName = opts[0].MMT.OwnerName()
			}
		}
		resolved.status = opts[0].Status
		resolved.machine = string(opts[0].Machine)
		resolved.command = opts[0].Command
		resolved.image = opts[0].Image
		resolved.publicIP = opts[0].PublicIP
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
		resolved.scratchDisks = opts[0].ScratchDisks
	}
	return resolved
}

func applyJobWaitOptions(opts ...JobWaitOptions) jobWaitOptions {
	resolved := jobWaitOptions{interval: 5 * time.Second}
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

func validateJobComputeEnvironment(command string, opts jobOptions) error {
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
	} else if opts.image == "" {
		return errors.New("either image or studio must be provided")
	} else if err := validateArtifacts(opts.artifactsSource, opts.artifactsDest); err != nil {
		return err
	}
	if err := validateScratchDisks(opts); err != nil {
		return err
	}
	return nil
}

func validateScratchDisks(opts jobOptions) error {
	if len(opts.scratchDisks) == 0 {
		return nil
	}
	if opts.studioID == "" {
		return errors.New("scratch_disks are only supported within a studio job")
	}
	if len(opts.scratchDisks) > 5 {
		return errors.New("scratch_disk may only contain up to 5 elements")
	}
	for _, disk := range opts.scratchDisks {
		if disk.SizeGB > 50000 {
			return errors.New("scratch_disk size cannot exceed 50TiB")
		}
		normalizedPath := strings.ReplaceAll(disk.Path, "\\", "/")
		for _, part := range strings.Split(normalizedPath, "/") {
			if part == ".." {
				return errors.New("scratch_disk path cannot contain '..'")
			}
		}
		cleanPath := path.Clean(normalizedPath)
		if path.IsAbs(cleanPath) && cleanPath != "/teamspace/scratch" && !strings.HasPrefix(cleanPath, "/teamspace/scratch/") {
			return errors.New("scratch_disk paths must be relative to /teamspace/scratch")
		}
	}
	return nil
}

func jobFromModel(model *models.V1Job, opts jobOptions) *Job {
	if model == nil {
		return nil
	}
	result := &Job{
		id:          model.ID,
		name:        model.Name,
		teamspaceID: model.ProjectID,
		teamspace:   opts.teamspaceName,
		ownerName:   opts.ownerName,
		status:      model.State,
		mmtID:       model.MultiMachineJobID,
		publicIP:    model.PublicIPAddress,
		totalCost:   model.TotalCost,
	}
	if model.Spec != nil {
		result.machine = model.Spec.InstanceName
		result.command = model.Spec.Command
		result.image = model.Spec.Image
		result.studioID = model.Spec.CloudspaceID
		result.artifactsSource = model.Spec.ArtifactsSource
		result.artifactsDestination = model.Spec.ArtifactsDestination
	}
	return result
}

func isJobTerminalStatus(status string) bool {
	switch strings.ToLower(status) {
	case "completed", "stopped", "failed":
		return true
	default:
		return false
	}
}

func jobSpec(machine, command string, opts jobOptions) *models.V1JobSpec {
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
		PathMappings:                jobPathMappings(opts),
		RequestedRunDurationSeconds: maxRuntime(opts.maxRuntime),
		Spot:                        opts.interruptible,
		Volumes:                     scratchVolumes(opts.scratchDisks),
	}
}

func jobPathMappings(opts jobOptions) []*models.V1PathMapping {
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

func artifactDestinationPath(destination string) string {
	parts := strings.Split(destination, ":")
	if len(parts) != 3 {
		return ""
	}
	return fmt.Sprintf("/teamspace/%s_connections/%s/%s", parts[0], parts[1], strings.TrimLeft(parts[2], "/"))
}

func scratchVolumes(disks []ScratchDisk) []*models.V1Volume {
	if len(disks) == 0 {
		return nil
	}
	result := make([]*models.V1Volume, 0, len(disks))
	for _, disk := range disks {
		result = append(result, &models.V1Volume{
			Ephemeral: true,
			Path:      scratchPath(disk.Path),
			SizeGb:    strconv.Itoa(disk.SizeGB),
		})
	}
	return result
}

func scratchPath(path string) string {
	if path == "" || strings.HasPrefix(path, "/teamspace/scratch/") {
		return path
	}
	return "/teamspace/scratch/" + strings.TrimPrefix(path, "/")
}
