package lit

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	sdkapi "github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/cloud_space_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/projects_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/models"
	"github.com/lightning-ai/sdk/go/internal/sdkclient"
)

// Studio represents a Lightning Studio.
type Studio struct {
	id            string
	name          string
	status        string
	teamspaceID   string
	teamspace     teamspaceRef
	cloud         string
	machine       string
	interruptible bool
	autoSleep     bool
	autoSleepTime int
	env           map[string]string

	interruptibleSet bool
}

// RunAndDetachOptions configures detached command execution polling.
type RunAndDetachOptions struct {
	// Timeout limits how long RunAndDetach waits for command completion.
	Timeout time.Duration
	// CheckInterval controls how often RunAndDetach polls command status.
	CheckInterval time.Duration
}

type studioOptions struct {
	id               string
	name             string
	status           string
	teamspaceID      string
	teamspaceName    string
	ownerName        string
	cloud            string
	machine          string
	interruptible    bool
	interruptibleSet bool
	autoSleep        bool
	autoSleepTime    int
	env              map[string]string
}

type switchMachineOptions struct {
	cloud         string
	interruptible bool
}

type startStudioOptions struct {
	machine          string
	interruptible    bool
	interruptibleSet bool
	maxRuntime       int
}

type duplicateStudioOptions struct {
	name          string
	teamspaceID   string
	teamspaceName string
}

type teamspaceRef struct {
	id        string
	name      string
	ownerName string
}

type studioFields struct {
	ID               string
	Name             string
	Status           string
	TeamspaceID      string
	Teamspace        string
	OwnerName        string
	Cloud            string
	Machine          string
	Interruptible    bool
	AutoSleep        bool
	AutoSleepTime    int
	Env              map[string]string
	interruptibleSet bool
}

// StudioOptions configures studio lookup and creation.
type StudioOptions struct {
	// ID resolves an existing studio directly without looking it up by name.
	ID string
	// Teamspace scopes studio lookup or creation to a specific teamspace.
	Teamspace *Teamspace
	// Cloud selects a cloud account or provider for the studio.
	Cloud string
	// Machine selects the compute type used when creating or seeding a studio handle.
	Machine Machine
	// Interruptible overrides whether the studio runs on interruptible capacity.
	Interruptible *bool
	// Status seeds the latest known state for ID-based handles.
	Status string
	// AutoSleep enables or disables studio auto-sleep.
	AutoSleep bool
	// AutoSleepTime sets the auto-sleep timeout in minutes.
	AutoSleepTime int
	// Env seeds environment variables on the studio handle.
	Env map[string]string
}

// StartStudioOptions configures studio start behavior.
type StartStudioOptions struct {
	// Machine overrides the machine type used to start the studio.
	Machine Machine
	// Interruptible overrides whether the started studio uses interruptible capacity.
	Interruptible *bool
	// MaxRuntime limits the studio runtime in seconds.
	MaxRuntime int
}

// SwitchMachineOptions configures a studio machine switch.
type SwitchMachineOptions struct {
	// Cloud selects a cloud account or provider for the new machine.
	Cloud string
	// Interruptible overrides whether the new machine uses interruptible capacity.
	Interruptible *bool
}

// DuplicateStudioOptions configures studio duplication.
type DuplicateStudioOptions struct {
	// Name sets the duplicated studio name.
	Name string
	// Teamspace sets the destination teamspace for the duplicate.
	Teamspace *Teamspace
}

// GetStudio returns an existing studio by name or ID.
func GetStudio(name string, opts ...StudioOptions) (*Studio, error) {
	resolved := applyStudioOptions(opts...)
	if name == "" && resolved.id == "" {
		return nil, errors.New("studio requires name or ID")
	}
	if resolved.id != "" {
		return newStudio(studioFields{
			ID:               resolved.id,
			Name:             name,
			Status:           resolved.status,
			TeamspaceID:      resolved.teamspaceID,
			Teamspace:        resolved.teamspaceName,
			OwnerName:        resolved.ownerName,
			Cloud:            resolved.cloud,
			Machine:          resolved.machine,
			Interruptible:    resolved.interruptible,
			interruptibleSet: resolved.interruptibleSet,
			AutoSleep:        resolved.autoSleep,
			AutoSleepTime:    resolved.autoSleepTime,
			Env:              cloneMap(resolved.env),
		}), nil
	}
	if resolved.teamspaceID == "" {
		return nil, errors.New("studio requires teamspace when ID is not provided")
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	params := cloud_space_service.NewCloudSpaceServiceGetCloudSpaceByNameParamsWithContext(context.Background()).
		WithCloudspaceName(name).
		WithProjectName(firstNonEmpty(resolved.teamspaceName, "-")).
		WithUserName(firstNonEmpty(resolved.ownerName, "-"))
	if resolved.teamspaceID != "" {
		params = params.WithProjectID(&resolved.teamspaceID)
	}
	resp, err := api.CloudSpaceService.CloudSpaceServiceGetCloudSpaceByName(params)
	if err != nil {
		return nil, err
	}
	return studioFromResponse(resp.Payload, resolved)
}

// CreateStudio creates a new studio.
func CreateStudio(name string, opts ...StudioOptions) (*Studio, error) {
	resolved := applyStudioOptions(opts...)
	if name == "" {
		return nil, errors.New("studio create requires name")
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	if resolved.teamspaceID == "" {
		return nil, errors.New("studio create requires teamspace")
	}
	body := &models.CloudSpaceServiceCreateCloudSpaceBody{
		ClusterID:   resolved.cloud,
		ComputeName: resolved.machine,
		DisplayName: name,
		Name:        name,
		Spot:        resolved.interruptible,
	}
	resp, err := api.CloudSpaceService.CloudSpaceServiceCreateCloudSpace(
		cloud_space_service.NewCloudSpaceServiceCreateCloudSpaceParamsWithContext(context.Background()).
			WithProjectID(resolved.teamspaceID).
			WithBody(body),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("create studio returned empty payload")
	}
	return studioFromCloudSpace(resp.Payload, resolved), nil
}

// StartStudio starts a studio.
func StartStudio(s *Studio, opts ...StartStudioOptions) error {
	if s == nil {
		return errors.New("start studio requires studio")
	}
	return s.Start(opts...)
}

// SwitchStudioMachine switches a studio to another machine type.
func SwitchStudioMachine(s *Studio, machine Machine, opts ...SwitchMachineOptions) error {
	if s == nil {
		return errors.New("switch studio machine requires studio")
	}
	return s.SwitchMachine(machine, opts...)
}

func newStudio(fields studioFields) *Studio {
	result := &Studio{
		id:               fields.ID,
		name:             fields.Name,
		status:           fields.Status,
		teamspaceID:      fields.TeamspaceID,
		teamspace:        teamspaceRef{id: fields.TeamspaceID, name: fields.Teamspace, ownerName: fields.OwnerName},
		cloud:            fields.Cloud,
		machine:          fields.Machine,
		interruptible:    fields.Interruptible,
		autoSleep:        fields.AutoSleep,
		autoSleepTime:    fields.AutoSleepTime,
		env:              cloneMap(fields.Env),
		interruptibleSet: fields.interruptibleSet,
	}
	return result
}

func (s *Studio) teamspaceReference() teamspaceRef {
	if s == nil {
		return teamspaceRef{}
	}
	return s.teamspace
}

// ID returns the studio ID.
func (s *Studio) ID() string {
	if s == nil {
		return ""
	}
	return s.id
}

// TeamspaceID returns the owning teamspace ID.
func (s *Studio) TeamspaceID() string {
	if s == nil {
		return ""
	}
	return s.teamspaceID
}

// Name returns the studio name.
func (s *Studio) Name() string {
	if s == nil {
		return ""
	}
	return s.name
}

// Status returns the latest known studio status.
func (s *Studio) Status() string {
	if s == nil {
		return ""
	}
	return s.status
}

// Teamspace returns the owning teamspace name.
func (s *Studio) Teamspace() string {
	if s == nil {
		return ""
	}
	return s.teamspace.name
}

// OwnerName returns the owning user or organization name.
func (s *Studio) OwnerName() string {
	if s == nil {
		return ""
	}
	return s.teamspace.ownerName
}

// Cloud returns the configured cloud account ID.
func (s *Studio) Cloud() string {
	if s == nil {
		return ""
	}
	return s.cloud
}

// Machine returns the configured machine.
func (s *Studio) Machine() string {
	if s == nil {
		return ""
	}
	return s.machine
}

// Interruptible reports whether the studio uses interruptible capacity.
func (s *Studio) Interruptible() bool {
	if s == nil {
		return false
	}
	return s.interruptible
}

// AutoSleep reports whether auto sleep is enabled.
func (s *Studio) AutoSleep() bool {
	if s == nil {
		return false
	}
	return s.autoSleep
}

// AutoSleepTime returns the auto sleep timeout in seconds.
func (s *Studio) AutoSleepTime() int {
	if s == nil {
		return 0
	}
	return s.autoSleepTime
}

// Env returns a copy of the studio environment.
func (s *Studio) Env() map[string]string {
	if s == nil {
		return nil
	}
	return cloneMap(s.env)
}

// String returns a compact human-readable representation.
func (s *Studio) String() string {
	if s == nil {
		return "Studio(name=, teamspace=)"
	}
	teamspace := s.teamspaceReference()
	return fmt.Sprintf("Studio(name=%s, teamspace=Teamspace(name=%s, owner=%s))", s.Name(), teamspace.name, teamspace.ownerName)
}

// Equal reports whether two studio handles refer to the same public state.
func (s *Studio) Equal(other *Studio) bool {
	if s == nil || other == nil {
		return s == other
	}
	return s.Name() == other.Name() && s.teamspaceReference() == other.teamspaceReference()
}

// Start starts the studio.
func (s *Studio) Start(opts ...StartStudioOptions) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio start requires teamspace ID and studio ID")
	}
	resolved := applyStartStudioOptions(opts...)
	machine := firstNonEmpty(resolved.machine, s.machine)
	if machine == "" {
		machine = "CPU"
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	interruptible := s.interruptible
	if override := os.Getenv("LIGHTNING_INTERRUPTIBLE_OVERRIDE"); override != "" {
		interruptible = strings.ToLower(override) == "true"
	} else if resolved.interruptibleSet {
		interruptible = resolved.interruptible
	} else if !s.interruptibleSet {
		interruptible, err = resolveDefaultStartInterruptible(api, s.teamspaceID)
		if err != nil {
			return err
		}
	}
	body := &models.CloudSpaceServiceStartCloudSpaceInstanceBody{
		ComputeConfig: &models.V1UserRequestedComputeConfig{
			ClusterOverride:             s.cloud,
			Name:                        machine,
			RequestedRunDurationSeconds: maxRuntime(resolved.maxRuntime),
			Spot:                        interruptible,
		},
	}
	_, err = api.CloudSpaceService.CloudSpaceServiceStartCloudSpaceInstance(
		cloud_space_service.NewCloudSpaceServiceStartCloudSpaceInstanceParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id).
			WithBody(body),
	)
	if err != nil {
		return err
	}
	s.status = "running"
	s.machine = machine
	s.interruptible = interruptible
	s.interruptibleSet = true
	return nil
}

// SwitchMachine changes the studio machine.
func (s *Studio) SwitchMachine(machine Machine, opts ...SwitchMachineOptions) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio switch machine requires teamspace ID and studio ID")
	}
	machineName := string(machine)
	if machineName == "" {
		return errors.New("studio switch machine requires machine")
	}
	resolved := applySwitchMachineOptions(opts...)
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	body := &models.CloudSpaceServiceUpdateCloudSpaceInstanceConfigBody{
		ComputeConfig: &models.V1UserRequestedComputeConfig{
			ClusterOverride: resolved.cloud,
			Name:            machineName,
			Spot:            resolved.interruptible,
		},
	}
	_, err = api.CloudSpaceService.CloudSpaceServiceUpdateCloudSpaceInstanceConfig(
		cloud_space_service.NewCloudSpaceServiceUpdateCloudSpaceInstanceConfigParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id).
			WithBody(body),
	)
	if err != nil {
		return err
	}
	s.machine = machineName
	s.interruptible = resolved.interruptible
	if resolved.cloud != "" {
		s.cloud = resolved.cloud
	}
	return nil
}

// Stop stops the studio.
func (s *Studio) Stop() error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio stop requires teamspace ID and studio ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	_, err = api.CloudSpaceService.CloudSpaceServiceStopCloudSpaceInstance(
		cloud_space_service.NewCloudSpaceServiceStopCloudSpaceInstanceParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id),
	)
	if err != nil {
		return err
	}
	s.status = "stopped"
	return nil
}

// Delete deletes the studio.
func (s *Studio) Delete() error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio delete requires teamspace ID and studio ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	_, err = api.CloudSpaceService.CloudSpaceServiceDeleteCloudSpace(
		cloud_space_service.NewCloudSpaceServiceDeleteCloudSpaceParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id),
	)
	return err
}

// PublicIP returns the current studio public IP when available.
func (s *Studio) PublicIP() (string, error) {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return "", errors.New("studio public IP requires teamspace ID and studio ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return "", err
	}
	resp, err := api.CloudSpaceService.CloudSpaceServiceGetCloudSpaceInstanceStatus(
		cloud_space_service.NewCloudSpaceServiceGetCloudSpaceInstanceStatusParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id),
	)
	if err != nil {
		return "", err
	}
	if resp.Payload == nil || resp.Payload.InUse == nil {
		return "", nil
	}
	return resp.Payload.InUse.PublicIPAddress, nil
}

// DownloadFile downloads a file from the studio.
func (s *Studio) DownloadFile(remotePath, filePath string) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio download file requires teamspace ID and studio ID")
	}
	if remotePath == "" {
		return errors.New("studio download file requires remote path")
	}
	if filePath == "" {
		filePath = remotePath
	}
	api, err := sdkclient.NewRaw()
	if err != nil {
		return err
	}
	query := url.Values{
		"key": []string{sanitizeStudioRemotePath(remotePath, s.id)},
	}
	if s.cloud != "" {
		query.Set("clusterId", s.cloud)
	}
	if token := os.Getenv("LIGHTNING_AUTH_TOKEN"); token != "" {
		query.Set("token", token)
	}
	return api.Download(context.Background(), studioArtifactBlobPath(s.teamspaceID, s.id, remotePath), query, filePath)
}

// DownloadFolder downloads a folder from the studio.
func (s *Studio) DownloadFolder(remotePath, targetPath string) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio download folder requires teamspace ID and studio ID")
	}
	if targetPath == "" {
		targetPath = remotePath
	}
	api, err := sdkclient.NewRaw()
	if err != nil {
		return err
	}
	remotePath = strings.Trim(remotePath, "/")
	query := url.Values{"recursive": []string{"true"}}
	if token := os.Getenv("LIGHTNING_AUTH_TOKEN"); token != "" {
		query.Set("token", token)
	}
	var tree artifactTreeResponse
	if err := api.Do(context.Background(), http.MethodGet, studioArtifactTreePath(s.teamspaceID, s.id, remotePath), query, nil, &tree); err != nil {
		return err
	}
	for _, item := range tree.Tree {
		if item.Type != "blob" || item.Path == "" {
			continue
		}
		remoteFilePath := item.Path
		if remotePath != "" {
			remoteFilePath = remotePath + "/" + strings.TrimLeft(item.Path, "/")
		}
		targetFilePath := filepath.Join(targetPath, filepath.FromSlash(item.Path))
		if err := api.Download(context.Background(), studioArtifactBlobPath(s.teamspaceID, s.id, remoteFilePath), downloadQuery(), targetFilePath); err != nil {
			return err
		}
	}
	return nil
}

// UploadFile uploads a file to the studio.
func (s *Studio) UploadFile(filePath, remotePath string) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio upload file requires teamspace ID and studio ID")
	}
	if filePath == "" {
		return errors.New("studio upload file requires file path")
	}
	if remotePath == "" {
		remotePath = filepath.Base(filePath)
	}
	api, err := sdkclient.NewRaw()
	if err != nil {
		return err
	}
	query := url.Values{}
	if token := os.Getenv("LIGHTNING_AUTH_TOKEN"); token != "" {
		query.Set("token", token)
	}
	// Completion makes the file show up in a running Studio.
	return api.Upload(context.Background(), studioArtifactScopePath(s.teamspaceID, s.id), strings.TrimLeft(remotePath, "/"), query, filePath, sdkclient.UploadOptions{NotifyCompletion: true})
}

// UploadFolder uploads a folder to the studio.
func (s *Studio) UploadFolder(folderPath, remotePath string) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio upload folder requires teamspace ID and studio ID")
	}
	if folderPath == "" {
		return errors.New("studio upload folder requires folder path")
	}
	info, err := os.Stat(folderPath)
	if err != nil {
		return err
	}
	if !info.IsDir() {
		return fmt.Errorf("cannot upload file as folder: %s", folderPath)
	}
	var files []string
	if err := filepath.WalkDir(folderPath, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		files = append(files, path)
		return nil
	}); err != nil {
		return err
	}
	sort.Strings(files)
	for _, filePath := range files {
		relativePath, err := filepath.Rel(folderPath, filePath)
		if err != nil {
			return err
		}
		remoteFilePath := filepath.ToSlash(relativePath)
		if remotePath != "" {
			remoteFilePath = strings.TrimRight(remotePath, "/") + "/" + remoteFilePath
		}
		if err := s.UploadFile(filePath, remoteFilePath); err != nil {
			return err
		}
	}
	return nil
}

// RunWithExitCode runs commands in the studio and returns output plus exit code.
func (s *Studio) RunWithExitCode(commands ...string) (string, int, error) {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return "", 0, errors.New("studio run requires teamspace ID and studio ID")
	}
	if s.status != "" && !isRunningStatus(s.status) {
		return "", 0, fmt.Errorf("cannot run command in studio %q with status %q", s.name, s.status)
	}
	api, err := sdkclient.New()
	if err != nil {
		return "", 0, err
	}
	submitResp, err := api.CloudSpaceService.CloudSpaceServiceExecuteCommandInCloudSpace(
		cloud_space_service.NewCloudSpaceServiceExecuteCommandInCloudSpaceParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id).
			WithBody(&models.CloudSpaceServiceExecuteCommandInCloudSpaceBody{
				Command:  strings.Join(commands, "; "),
				Detached: true,
			}),
	)
	if err != nil {
		return "", 0, err
	}
	if submitResp.Payload == nil {
		return "", 0, errors.New("submit studio command returned empty payload")
	}
	if submitResp.Payload.SessionName == "" {
		return "", 0, errors.New("submit studio command returned empty session name")
	}

	for {
		statusResp, err := api.CloudSpaceService.CloudSpaceServiceGetLongRunningCommandInCloudSpace(
			cloud_space_service.NewCloudSpaceServiceGetLongRunningCommandInCloudSpaceParamsWithContext(context.Background()).
				WithProjectID(s.teamspaceID).
				WithID(s.id).
				WithSession(submitResp.Payload.SessionName),
		)
		if err != nil {
			return "", 0, err
		}
		if statusResp.Payload == nil {
			return "", 0, errors.New("get studio command status returned empty payload")
		}
		if statusResp.Payload.ExitCode == -1 {
			time.Sleep(time.Second)
			continue
		}
		return strings.TrimSpace(statusResp.Payload.Output), int(statusResp.Payload.ExitCode), nil
	}
}

// Run runs commands in the studio and returns output when they succeed.
func (s *Studio) Run(commands ...string) (string, error) {
	output, exitCode, err := s.RunWithExitCode(commands...)
	if err != nil {
		return "", err
	}
	if exitCode != 0 {
		return "", errors.New(output)
	}
	return output, nil
}

// RunAndDetach starts commands in the studio and polls briefly for completion.
func (s *Studio) RunAndDetach(commands []string, opts RunAndDetachOptions) (string, int, error) {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return "", 0, errors.New("studio run and detach requires teamspace ID and studio ID")
	}
	if s.status != "" && !isRunningStatus(s.status) {
		return "", 0, fmt.Errorf("cannot run command in studio %q with status %q", s.name, s.status)
	}
	if opts.Timeout == 0 {
		opts.Timeout = 10 * time.Second
	}
	if opts.CheckInterval == 0 {
		opts.CheckInterval = time.Second
	}
	if opts.CheckInterval > opts.Timeout {
		return "", 0, errors.New("check interval must be less than timeout")
	}
	api, err := sdkclient.New()
	if err != nil {
		return "", 0, err
	}
	submitResp, err := api.CloudSpaceService.CloudSpaceServiceExecuteCommandInCloudSpace(
		cloud_space_service.NewCloudSpaceServiceExecuteCommandInCloudSpaceParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id).
			WithBody(&models.CloudSpaceServiceExecuteCommandInCloudSpaceBody{
				Command:  strings.Join(commands, "; "),
				Detached: true,
			}),
	)
	if err != nil {
		return "", 0, err
	}
	if submitResp.Payload == nil {
		return "", 0, errors.New("submit studio command returned empty payload")
	}
	if submitResp.Payload.SessionName == "" {
		return "", 0, errors.New("submit studio command returned empty session name")
	}

	output := ""
	exitCode := -1
	deadline := time.Now().Add(opts.Timeout)
	for time.Now().Before(deadline) {
		statusResp, err := api.CloudSpaceService.CloudSpaceServiceGetLongRunningCommandInCloudSpace(
			cloud_space_service.NewCloudSpaceServiceGetLongRunningCommandInCloudSpaceParamsWithContext(context.Background()).
				WithProjectID(s.teamspaceID).
				WithID(s.id).
				WithSession(submitResp.Payload.SessionName),
		)
		if err != nil {
			return "", 0, err
		}
		if statusResp.Payload == nil {
			return "", 0, errors.New("get studio command status returned empty payload")
		}
		if statusResp.Payload.ExitCode == -1 {
			time.Sleep(opts.CheckInterval)
			continue
		}
		exitCode = int(statusResp.Payload.ExitCode)
		output += statusResp.Payload.Output
		if exitCode != 0 {
			return output, exitCode, fmt.Errorf("command failed with exit code %d. Output: %s", exitCode, statusResp.Payload.Output)
		}
		return output, exitCode, nil
	}
	return output, exitCode, nil
}

// Rename renames the studio.
func (s *Studio) Rename(newName string) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio rename requires teamspace ID and studio ID")
	}
	if newName == "" {
		return errors.New("studio rename requires name")
	}
	if newName == s.name {
		return nil
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	resp, err := api.CloudSpaceService.CloudSpaceServiceUpdateCloudSpace(
		cloud_space_service.NewCloudSpaceServiceUpdateCloudSpaceParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id).
			WithBody(&models.CloudSpaceServiceUpdateCloudSpaceBody{DisplayName: newName}),
	)
	if err != nil {
		return err
	}
	if resp.Payload == nil {
		s.name = newName
		return nil
	}
	updated := studioFromCloudSpace(resp.Payload, studioOptions{
		teamspaceID:   s.teamspaceID,
		teamspaceName: s.Teamspace(),
		ownerName:     s.OwnerName(),
		cloud:         s.cloud,
		machine:       s.machine,
		interruptible: s.interruptible,
	})
	if updated != nil {
		*s = *updated
	}
	return nil
}

// Duplicate forks the studio into a new studio.
func (s *Studio) Duplicate(opts ...DuplicateStudioOptions) (*Studio, error) {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return nil, errors.New("studio duplicate requires teamspace ID and studio ID")
	}
	resolved := applyDuplicateStudioOptions(opts...)
	targetTeamspaceID := firstNonEmpty(resolved.teamspaceID, s.teamspaceID)
	targetTeamspaceName := firstNonEmpty(resolved.teamspaceName, s.Teamspace())
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	resp, err := api.CloudSpaceService.CloudSpaceServiceForkCloudSpace(
		cloud_space_service.NewCloudSpaceServiceForkCloudSpaceParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id).
			WithBody(&models.CloudSpaceServiceForkCloudSpaceBody{
				NewName:         resolved.name,
				TargetProjectID: targetTeamspaceID,
			}),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("duplicate studio returned empty payload")
	}
	return studioFromCloudSpace(resp.Payload, studioOptions{
		teamspaceID:   targetTeamspaceID,
		teamspaceName: targetTeamspaceName,
		ownerName:     s.OwnerName(),
		cloud:         s.cloud,
		machine:       s.machine,
		interruptible: s.interruptible,
	}), nil
}

// SetEnv replaces or patches the studio environment.
func (s *Studio) SetEnv(newEnv map[string]string, partial bool) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio set env requires teamspace ID and studio ID")
	}
	updatedEnv := map[string]string{}
	if partial {
		for key, value := range s.env {
			updatedEnv[key] = value
		}
	}
	for key, value := range newEnv {
		updatedEnv[key] = value
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	resp, err := api.CloudSpaceService.CloudSpaceServiceUpdateCloudSpace(
		cloud_space_service.NewCloudSpaceServiceUpdateCloudSpaceParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id).
			WithBody(&models.CloudSpaceServiceUpdateCloudSpaceBody{Env: envVars(updatedEnv)}),
	)
	if err != nil {
		return err
	}
	s.env = updatedEnv
	if resp.Payload == nil {
		return nil
	}
	updated := studioFromCloudSpace(resp.Payload, studioOptions{
		teamspaceID:   s.teamspaceID,
		teamspaceName: s.Teamspace(),
		ownerName:     s.OwnerName(),
		cloud:         s.cloud,
		machine:       s.machine,
		interruptible: s.interruptible,
	})
	if updated != nil {
		*s = *updated
	}
	return nil
}

// AvailablePlugins lists plugins available for installation.
func (s *Studio) AvailablePlugins() (map[string]string, error) {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return nil, errors.New("studio available plugins requires teamspace ID and studio ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	response, err := api.CloudSpaceService.CloudSpaceServiceListAvailablePlugins(
		cloud_space_service.NewCloudSpaceServiceListAvailablePluginsParamsWithContext(context.Background()).
			WithProjectID(&s.teamspaceID).
			WithID(&s.id),
	)
	if err != nil {
		return nil, err
	}
	if response.Payload == nil || response.Payload.Plugins == nil {
		return map[string]string{}, nil
	}
	return response.Payload.Plugins, nil
}

// InstalledPlugins lists installed plugins.
func (s *Studio) InstalledPlugins() (map[string]string, error) {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return nil, errors.New("studio installed plugins requires teamspace ID and studio ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	response, err := api.CloudSpaceService.CloudSpaceServiceListInstalledPlugins(
		cloud_space_service.NewCloudSpaceServiceListInstalledPluginsParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id),
	)
	if err != nil {
		return nil, err
	}
	if response.Payload == nil || response.Payload.Plugins == nil {
		return map[string]string{}, nil
	}
	return response.Payload.Plugins, nil
}

// InstallPlugin installs a studio plugin.
func (s *Studio) InstallPlugin(pluginName string) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio install plugin requires teamspace ID and studio ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	response, err := api.CloudSpaceService.CloudSpaceServiceInstallPlugin(
		cloud_space_service.NewCloudSpaceServiceInstallPluginParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id).
			WithPluginID(pluginName),
	)
	if err != nil {
		return err
	}
	if response.Payload == nil || response.Payload.State != "installation_success" || response.Payload.Error != "" {
		return fmt.Errorf("failed to install plugin %s: %s", pluginName, pluginError(response.Payload))
	}
	return nil
}

// RunPlugin executes a studio plugin.
func (s *Studio) RunPlugin(pluginName string) (string, error) {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return "", errors.New("studio run plugin requires teamspace ID and studio ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return "", err
	}
	response, err := api.CloudSpaceService.CloudSpaceServiceExecutePlugin(
		cloud_space_service.NewCloudSpaceServiceExecutePluginParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id).
			WithPluginID(pluginName),
	)
	if err != nil {
		return "", err
	}
	if response.Payload == nil || response.Payload.State != "execution_success" || response.Payload.Error != "" {
		return "", fmt.Errorf("failed to execute plugin %s: %s", pluginName, pluginError(response.Payload))
	}
	var additionalInfo struct {
		Port int `json:"port"`
	}
	if err := json.Unmarshal([]byte(response.Payload.AdditionalInfo), &additionalInfo); err != nil {
		return "", err
	}
	switch {
	case additionalInfo.Port > 0:
		return fmt.Sprintf("Plugin %s is interactive. Have a look at https://%d-%s.cloudspaces.litng.ai", pluginName, additionalInfo.Port, s.id), nil
	case additionalInfo.Port < 0:
		return "This plugin can only be used on the browser interface of a Studio!", nil
	default:
		return fmt.Sprintf("Successfully executed plugin %s", pluginName), nil
	}
}

// UninstallPlugin uninstalls a studio plugin.
func (s *Studio) UninstallPlugin(pluginName string) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio uninstall plugin requires teamspace ID and studio ID")
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	response, err := api.CloudSpaceService.CloudSpaceServiceUninstallPlugin(
		cloud_space_service.NewCloudSpaceServiceUninstallPluginParamsWithContext(context.Background()).
			WithProjectID(s.teamspaceID).
			WithID(s.id).
			WithPluginID(pluginName),
	)
	if err != nil {
		return err
	}
	if response.Payload == nil || response.Payload.State != "uninstallation_success" || response.Payload.Error != "" {
		return fmt.Errorf("failed to uninstall plugin %s: %s", pluginName, pluginError(response.Payload))
	}
	return nil
}

// SetAutoSleep enables or disables studio auto sleep.
func (s *Studio) SetAutoSleep(enabled bool) error {
	return s.updateSleepConfig(&enabled, nil)
}

// SetAutoSleepTime sets the studio auto sleep timeout in seconds.
func (s *Studio) SetAutoSleepTime(seconds int) error {
	if seconds <= 0 {
		return errors.New("studio auto sleep time requires positive seconds")
	}
	return s.updateSleepConfig(nil, &seconds)
}

// SetAutoShutdown enables or disables studio auto shutdown.
func (s *Studio) SetAutoShutdown(enabled bool) error {
	return s.SetAutoSleep(enabled)
}

// SetAutoShutdownTime sets the studio auto shutdown timeout in seconds.
func (s *Studio) SetAutoShutdownTime(seconds int) error {
	return s.SetAutoSleepTime(seconds)
}

func (s *Studio) updateSleepConfig(autoSleep *bool, autoSleepTime *int) error {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return errors.New("studio sleep config requires teamspace ID and studio ID")
	}
	api, err := sdkclient.NewRaw()
	if err != nil {
		return err
	}
	body := struct {
		DisableAutoShutdown *bool `json:"disableAutoShutdown,omitempty"`
		IdleShutdownSeconds *int  `json:"idleShutdownSeconds,omitempty"`
	}{
		IdleShutdownSeconds: autoSleepTime,
	}
	if autoSleep != nil {
		disableAutoShutdown := !*autoSleep
		body.DisableAutoShutdown = &disableAutoShutdown
	}
	var response models.V1CloudSpaceInstanceConfig
	if err := api.Do(context.Background(), http.MethodPut, sleepConfigPath(s.teamspaceID, s.id), nil, body, &response); err != nil {
		return err
	}
	s.applySleepConfig(&response)
	return nil
}

// RunJob creates a job from the studio environment.
func (s *Studio) RunJob(name string, machine Machine, command string, opts ...JobOptions) (*Job, error) {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return nil, errors.New("studio run job requires teamspace ID and studio ID")
	}
	resolved := JobOptions{
		Studio: s,
	}
	if len(opts) > 0 {
		resolved = opts[0]
		if resolved.Studio == nil {
			resolved.Studio = s
		}
	}
	return RunJob(name, machine, command, resolved)
}

// RunMMT creates an MMT from the studio environment.
func (s *Studio) RunMMT(name string, numMachines int64, machine Machine, command string, opts ...MMTOptions) (*MMT, error) {
	if s == nil || s.teamspaceID == "" || s.id == "" {
		return nil, errors.New("studio run mmt requires teamspace ID and studio ID")
	}
	resolved := MMTOptions{
		Studio: s,
	}
	if len(opts) > 0 {
		resolved = opts[0]
		if resolved.Studio == nil {
			resolved.Studio = s
		}
	}
	return RunMMT(name, numMachines, machine, command, resolved)
}

func applyStudioOptions(opts ...StudioOptions) studioOptions {
	var resolved studioOptions
	if len(opts) > 0 {
		resolved.id = opts[0].ID
		resolved.status = opts[0].Status
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
		resolved.cloud = opts[0].Cloud
		resolved.machine = string(opts[0].Machine)
		resolved.autoSleep = opts[0].AutoSleep
		resolved.autoSleepTime = opts[0].AutoSleepTime
		resolved.env = cloneMap(opts[0].Env)
		if opts[0].Interruptible != nil {
			resolved.interruptible = *opts[0].Interruptible
			resolved.interruptibleSet = true
		}
	}
	return resolved
}

func applyStartStudioOptions(opts ...StartStudioOptions) startStudioOptions {
	var resolved startStudioOptions
	if len(opts) > 0 {
		resolved.machine = string(opts[0].Machine)
		resolved.maxRuntime = opts[0].MaxRuntime
		if opts[0].Interruptible != nil {
			resolved.interruptible = *opts[0].Interruptible
			resolved.interruptibleSet = true
		}
	}
	return resolved
}

func applySwitchMachineOptions(opts ...SwitchMachineOptions) switchMachineOptions {
	var resolved switchMachineOptions
	if len(opts) > 0 {
		resolved.cloud = opts[0].Cloud
		if opts[0].Interruptible != nil {
			resolved.interruptible = *opts[0].Interruptible
		}
	}
	return resolved
}

func applyDuplicateStudioOptions(opts ...DuplicateStudioOptions) duplicateStudioOptions {
	var resolved duplicateStudioOptions
	if len(opts) > 0 {
		resolved.name = opts[0].Name
		if opts[0].Teamspace != nil {
			resolved.teamspaceID = opts[0].Teamspace.ID()
			resolved.teamspaceName = opts[0].Teamspace.Name()
		}
	}
	return resolved
}

func resolveDefaultStartInterruptible(api *sdkapi.LightningSdkAPI, teamspaceID string) (bool, error) {
	if teamspaceID == "" {
		return false, nil
	}
	resp, err := api.ProjectsService.ProjectsServiceGetProject(
		projects_service.NewProjectsServiceGetProjectParamsWithContext(context.Background()).
			WithID(teamspaceID),
	)
	if err != nil {
		return false, err
	}
	if resp.Payload == nil || resp.Payload.ProjectSettings == nil {
		return false, nil
	}
	return resp.Payload.ProjectSettings.StartStudioOnSpotInstance, nil
}

func studioFromResponse(response *models.V1CloudSpaceProjectResponse, opts studioOptions) (*Studio, error) {
	if response == nil || response.Cloudspace == nil {
		return nil, fmt.Errorf("studio lookup returned empty payload")
	}
	st := response.Cloudspace
	teamspaceID := opts.teamspaceID
	teamspaceName := opts.teamspaceName
	if response.Project != nil {
		teamspaceID = firstNonEmpty(teamspaceID, response.Project.ID)
		teamspaceName = firstNonEmpty(teamspaceName, response.Project.Name)
	}
	autoSleep, autoSleepTime := sleepConfig(st.CodeConfig)
	return newStudio(studioFields{
		ID:               st.ID,
		Name:             st.Name,
		Status:           cloudSpaceState(st),
		TeamspaceID:      firstNonEmpty(teamspaceID, st.ProjectID),
		Teamspace:        teamspaceName,
		OwnerName:        opts.ownerName,
		Cloud:            st.ClusterID,
		Machine:          opts.machine,
		Interruptible:    opts.interruptible,
		interruptibleSet: opts.interruptibleSet,
		AutoSleep:        autoSleep,
		AutoSleepTime:    autoSleepTime,
		Env:              envMap(st.Env),
	}), nil
}

func studioFromCloudSpace(st *models.V1CloudSpace, opts studioOptions) *Studio {
	autoSleep, autoSleepTime := sleepConfig(st.CodeConfig)
	return newStudio(studioFields{
		ID:               st.ID,
		Name:             st.Name,
		Status:           cloudSpaceState(st),
		TeamspaceID:      firstNonEmpty(st.ProjectID, opts.teamspaceID),
		Teamspace:        opts.teamspaceName,
		OwnerName:        opts.ownerName,
		Cloud:            firstNonEmpty(st.ClusterID, opts.cloud),
		Machine:          opts.machine,
		Interruptible:    opts.interruptible,
		interruptibleSet: opts.interruptibleSet,
		AutoSleep:        autoSleep,
		AutoSleepTime:    autoSleepTime,
		Env:              envMap(st.Env),
	})
}

func isRunningStatus(status string) bool {
	switch strings.ToLower(status) {
	case "running", "cloud_space_instance_state_running", "cloud_space_state_running":
		return true
	default:
		return false
	}
}

func envMap(env []*models.V1EnvVar) map[string]string {
	result := map[string]string{}
	for _, item := range env {
		if item == nil || item.Name == "" {
			continue
		}
		result[item.Name] = item.Value
	}
	return result
}

func sleepConfigPath(teamspaceID, studioID string) string {
	return "/v1/projects/" + url.PathEscape(teamspaceID) + "/cloudspaces/" + url.PathEscape(studioID) + "/sleepconfig"
}

func studioArtifactScopePath(teamspaceID, studioID string) string {
	return "/v1/projects/" + url.PathEscape(teamspaceID) + "/artifacts/cloudspaces/" + url.PathEscape(studioID)
}

func studioArtifactBlobPath(teamspaceID, studioID, remotePath string) string {
	return studioArtifactScopePath(teamspaceID, studioID) + "/blobs/" + strings.TrimLeft(remotePath, "/")
}

func studioArtifactTreePath(teamspaceID, studioID, remotePath string) string {
	return "/v1/projects/" + url.PathEscape(teamspaceID) + "/artifacts/cloudspaces/" + url.PathEscape(studioID) + "/trees/" + strings.TrimLeft(remotePath, "/")
}

func sanitizeStudioRemotePath(remotePath, studioID string) string {
	remotePath = strings.ReplaceAll(remotePath, "/teamspace/studios/this_studio/", "")
	return "/cloudspaces/" + studioID + "/code/content/" + strings.TrimLeft(remotePath, "/")
}

func downloadQuery() url.Values {
	query := url.Values{}
	if token := os.Getenv("LIGHTNING_AUTH_TOKEN"); token != "" {
		query.Set("token", token)
	}
	return query
}

func sleepConfig(config *models.V1CloudSpaceInstanceConfig) (bool, int) {
	if config == nil {
		return false, 0
	}
	return !config.DisableAutoShutdown, int(config.IdleShutdownSeconds)
}

func (s *Studio) applySleepConfig(config *models.V1CloudSpaceInstanceConfig) {
	if config == nil {
		return
	}
	s.autoSleep = !config.DisableAutoShutdown
	s.autoSleepTime = int(config.IdleShutdownSeconds)
}

func pluginError(plugin *models.V1Plugin) string {
	if plugin == nil {
		return "empty response"
	}
	return plugin.Error
}
