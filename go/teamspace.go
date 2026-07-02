package lit

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"

	sdkapi "github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/cloud_space_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/cluster_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/data_connection_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/jobs_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/projects_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client/secret_service"
	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/models"
	"github.com/lightning-ai/sdk/go/internal/sdkclient"
)

// Teamspace represents a Lightning AI teamspace.
type Teamspace struct {
	id                          string
	name                        string
	owner                       Owner
	defaultCloudAccount         string
	startStudiosOnInterruptible bool
}

// ConnectionType identifies the supported teamspace data connection backend.
type ConnectionType string

const (
	// ConnectionTypeEFS creates an EFS-backed teamspace connection.
	ConnectionTypeEFS ConnectionType = "EFS"
	// ConnectionTypeS3 identifies an S3-backed teamspace connection.
	ConnectionTypeS3 ConnectionType = "S3"
	// ConnectionTypeGCS identifies a GCS-backed teamspace connection.
	ConnectionTypeGCS ConnectionType = "GCS"

	// ConnectionTypeFilestore identifies a GCP Filestore-backed teamspace connection.
	ConnectionTypeFilestore ConnectionType = "FILESTORE"
)

// FolderLocation identifies where a managed teamspace folder should be created.
type FolderLocation string

const (
	// FolderLocationAWS creates an AWS-backed folder.
	FolderLocationAWS FolderLocation = "AWS"
	// FolderLocationGCP creates a GCP-backed folder.
	FolderLocationGCP FolderLocation = "GCP"
	// FolderLocationCloudAgnostic creates a cloud-agnostic folder.
	FolderLocationCloudAgnostic FolderLocation = "CLOUD_AGNOSTIC"
)

type teamspaceOptions struct {
	id                          string
	ownerID                     string
	ownerName                   string
	owner                       Owner
	defaultCloudAccount         string
	startStudiosOnInterruptible bool
}

func (o teamspaceOptions) ownerValue() Owner {
	if o.owner != nil {
		return o.owner
	}
	return nil
}

type connectionOptions struct {
	cloud    string
	region   string
	writable bool
}

type folderOptions struct {
	cloud    string
	location FolderLocation
}

// TeamspaceOptions configures teamspace lookup and creation.
type TeamspaceOptions struct {
	// ID resolves an existing teamspace directly without looking it up by name.
	ID string
	// Owner scopes teamspace lookup or creation to a user or organization.
	Owner Owner
	// DefaultCloudAccount stores the preferred cloud account for the teamspace handle.
	DefaultCloudAccount string
	// StartStudiosOnInterruptible controls the default interruptible setting for studios.
	StartStudiosOnInterruptible bool
}

// ConnectionOptions configures a teamspace data connection.
type ConnectionOptions struct {
	// Cloud selects the cloud account or provider for the connection.
	Cloud string
	// Region selects the cloud region for the connection.
	Region string
	// Writable overrides whether the connection is writable.
	Writable *bool
}

// FolderOptions configures a managed teamspace folder.
type FolderOptions struct {
	// Cloud selects the cloud account or provider for the folder.
	Cloud string
	// Location selects where the folder is created.
	Location FolderLocation
}

func newTeamspace(id, name string, owner Owner) *Teamspace {
	return &Teamspace{id: id, name: name, owner: owner}
}

func (t *Teamspace) requireID(action string) (string, error) {
	if t == nil || t.id == "" {
		return "", fmt.Errorf("teamspace %s requires ID", action)
	}
	return t.id, nil
}

// GetTeamspace returns an existing teamspace by name or ID.
func GetTeamspace(name string, opts ...TeamspaceOptions) (*Teamspace, error) {
	resolved := applyTeamspaceOptions(opts...)
	if name == "" && resolved.id == "" {
		return nil, errors.New("teamspace requires name or ID")
	}
	if resolved.id != "" {
		result := newTeamspace(resolved.id, name, resolved.ownerValue())
		result.defaultCloudAccount = resolved.defaultCloudAccount
		result.startStudiosOnInterruptible = resolved.startStudiosOnInterruptible
		return result, nil
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	ownerID, ownerName, err := resolveTeamspaceOwner(api, resolved)
	if err != nil {
		return nil, err
	}
	resolved.ownerID = ownerID
	resolved.ownerName = ownerName
	_, organization := resolved.owner.(*Organization)
	projectID, err := findTeamspaceID(api, name, ownerID, organization)
	if err != nil {
		return nil, err
	}
	resp, err := api.ProjectsService.ProjectsServiceGetProject(
		projects_service.NewProjectsServiceGetProjectParamsWithContext(context.Background()).
			WithID(projectID),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("get teamspace returned empty payload")
	}
	return teamspaceFromProject(resp.Payload, resolved.ownerValue()), nil
}

// CreateTeamspace creates a new teamspace.
func CreateTeamspace(name string, opts ...TeamspaceOptions) (*Teamspace, error) {
	resolved := applyTeamspaceOptions(opts...)
	if name == "" {
		return nil, errors.New("teamspace create requires name")
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	if resolved.ownerID == "" && resolved.id == "" {
		return nil, errors.New("teamspace create requires owner")
	}
	body := &models.V1CreateProjectRequest{Name: name}
	if _, ok := resolved.owner.(*Organization); ok {
		body.OrganizationID = resolved.ownerID
	}
	resp, err := api.ProjectsService.ProjectsServiceCreateProject(
		projects_service.NewProjectsServiceCreateProjectParamsWithContext(context.Background()).WithBody(body),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("create teamspace returned empty payload")
	}
	return teamspaceFromProject(resp.Payload, resolved.ownerValue()), nil
}

func teamspaceFromProject(project *models.V1Project, owner Owner) *Teamspace {
	if project == nil {
		return nil
	}
	result := newTeamspace(project.ID, project.Name, owner)
	applyProjectSettings(result, project)
	return result
}

// ID returns the teamspace ID.
func (t *Teamspace) ID() string {
	if t == nil {
		return ""
	}
	return t.id
}

// OwnerID returns the ID of the teamspace owner when it is available.
func (t *Teamspace) OwnerID() string {
	if t == nil {
		return ""
	}
	if t.owner == nil {
		return ""
	}
	return t.owner.ID()
}

// Name returns the teamspace name.
func (t *Teamspace) Name() string {
	if t == nil {
		return ""
	}
	return t.name
}

// Owner returns the owner object associated with the teamspace.
func (t *Teamspace) Owner() Owner {
	if t == nil {
		return nil
	}
	return t.owner
}

func (t *Teamspace) ownerName() string {
	if t == nil || t.owner == nil {
		return ""
	}
	return t.owner.Name()
}

// DefaultCloudAccount returns the configured default cloud account ID.
func (t *Teamspace) DefaultCloudAccount() string {
	if t == nil {
		return ""
	}
	return t.defaultCloudAccount
}

// StartStudiosOnInterruptible reports whether new studios should prefer interruptible machines.
func (t *Teamspace) StartStudiosOnInterruptible() bool {
	if t == nil {
		return false
	}
	return t.startStudiosOnInterruptible
}

// String returns a compact human-readable representation.
func (t *Teamspace) String() string {
	if t == nil {
		return "Teamspace(name=, owner=)"
	}
	ownerName := ""
	if t.owner != nil {
		ownerName = t.owner.Name()
	}
	return fmt.Sprintf("Teamspace(name=%s, owner=%s)", t.Name(), ownerName)
}

// Equal reports whether two teamspace handles refer to the same public state.
func (t *Teamspace) Equal(other *Teamspace) bool {
	if t == nil || other == nil {
		return t == other
	}
	return t.ID() == other.ID() && t.Name() == other.Name() && sameOwner(t.Owner(), other.Owner())
}

// Refresh reloads mutable teamspace settings from Lightning.
func (t *Teamspace) Refresh() error {
	id, err := t.requireID("refresh")
	if err != nil {
		return err
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	resp, err := api.ProjectsService.ProjectsServiceGetProject(
		projects_service.NewProjectsServiceGetProjectParamsWithContext(context.Background()).
			WithID(id),
	)
	if err != nil {
		return err
	}
	if resp.Payload == nil {
		return fmt.Errorf("get teamspace returned empty payload")
	}
	t.id = resp.Payload.ID
	t.name = resp.Payload.Name
	applyProjectSettings(t, resp.Payload)
	return nil
}

// CloudAccounts returns the names of cloud accounts bound to the teamspace.
func (t *Teamspace) CloudAccounts() ([]string, error) {
	id, err := t.requireID("cloud accounts")
	if err != nil {
		return nil, err
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	resp, err := api.ProjectsService.ProjectsServiceListProjectClusterBindings(
		projects_service.NewProjectsServiceListProjectClusterBindingsParamsWithContext(context.Background()).
			WithProjectID(id),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("list teamspace cloud accounts returned empty payload")
	}
	var result []string
	for _, cluster := range resp.Payload.Clusters {
		if cluster == nil {
			continue
		}
		result = append(result, cluster.ClusterName)
	}
	return result, nil
}

// CloudAccountNames returns the names of cloud accounts bound to the teamspace.
func (t *Teamspace) CloudAccountNames() ([]string, error) {
	return t.CloudAccounts()
}

// Clusters returns the names of cloud accounts bound to the teamspace.
func (t *Teamspace) Clusters() ([]string, error) {
	return t.CloudAccountNames()
}

// Machines lists available machine types for the cloud filter.
func (t *Teamspace) Machines(cloud string, machine Machine) ([]Machine, error) {
	return t.ListMachines(cloud, machine)
}

// ListMachines lists available machine types for the cloud filter.
func (t *Teamspace) ListMachines(cloud string, machine Machine) ([]Machine, error) {
	id, err := t.requireID("list machines")
	if err != nil {
		return nil, err
	}
	cloudAccounts, providerFilter, err := t.machineCloudAccounts(cloud)
	if err != nil {
		return nil, err
	}
	if len(cloudAccounts) == 0 {
		return nil, errors.New("could not resolve cloud account")
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	var result []Machine
	for _, cloudAccount := range cloudAccounts {
		resp, err := api.ClusterService.ClusterServiceListProjectClusterAccelerators(
			cluster_service.NewClusterServiceListProjectClusterAcceleratorsParamsWithContext(context.Background()).
				WithProjectID(id).
				WithID(cloudAccount),
		)
		if err != nil {
			return nil, err
		}
		if resp.Payload == nil {
			return nil, fmt.Errorf("list teamspace machines returned empty payload")
		}
		for _, accelerator := range resp.Payload.Accelerator {
			if accelerator == nil || accelerator.OutOfCapacity || !matchesProvider(accelerator, providerFilter) || !matchesMachine(accelerator, string(machine)) {
				continue
			}
			result = append(result, machineFromAccelerator(accelerator))
		}
	}
	return result, nil
}

// Studios lists studios in the teamspace.
func (t *Teamspace) Studios() ([]*Studio, error) {
	id, err := t.requireID("studios")
	if err != nil {
		return nil, err
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	var result []*Studio
	var pageToken string
	for {
		params := cloud_space_service.NewCloudSpaceServiceListCloudSpacesParamsWithContext(context.Background()).
			WithProjectID(id)
		if pageToken != "" {
			params = params.WithPageToken(&pageToken)
		}
		resp, err := api.CloudSpaceService.CloudSpaceServiceListCloudSpaces(params)
		if err != nil {
			return nil, err
		}
		if resp.Payload == nil {
			return nil, fmt.Errorf("list studios returned empty payload")
		}
		for _, cloudspace := range resp.Payload.Cloudspaces {
			if cloudspace == nil {
				continue
			}
			item := newStudio(studioFields{
				ID:          cloudspace.ID,
				Name:        cloudspace.Name,
				TeamspaceID: firstNonEmpty(cloudspace.ProjectID, id),
				Teamspace:   t.Name(),
				OwnerName:   t.ownerName(),
				Status:      cloudSpaceState(cloudspace),
				Cloud:       cloudspace.ClusterID,
			})
			result = append(result, item)
		}
		if resp.Payload.NextPageToken == "" {
			return result, nil
		}
		pageToken = resp.Payload.NextPageToken
	}
}

// Jobs lists single-machine jobs in the teamspace.
func (t *Teamspace) Jobs() ([]*Job, error) {
	id, err := t.requireID("jobs")
	if err != nil {
		return nil, err
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	standalone := true
	var result []*Job
	var pageToken string
	for {
		params := jobs_service.NewJobsServiceListJobsParamsWithContext(context.Background()).
			WithProjectID(id).
			WithStandalone(&standalone)
		if pageToken != "" {
			params = params.WithPageToken(&pageToken)
		}
		resp, err := api.JobsService.JobsServiceListJobs(params)
		if err != nil {
			return nil, err
		}
		if resp.Payload == nil {
			return nil, fmt.Errorf("list jobs returned empty payload")
		}
		for _, model := range resp.Payload.Jobs {
			if model == nil {
				continue
			}
			result = append(result, t.jobFromModel(model))
		}
		if resp.Payload.NextPageToken == "" {
			return result, nil
		}
		pageToken = resp.Payload.NextPageToken
	}
}

// MMTs lists multi-machine jobs in the teamspace.
func (t *Teamspace) MMTs() ([]*MMT, error) {
	return t.MultiMachineJobs()
}

// MultiMachineJobs lists multi-machine jobs in the teamspace.
func (t *Teamspace) MultiMachineJobs() ([]*MMT, error) {
	id, err := t.requireID("multi-machine jobs")
	if err != nil {
		return nil, err
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	resp, err := api.JobsService.JobsServiceListMultiMachineJobs(
		jobs_service.NewJobsServiceListMultiMachineJobsParamsWithContext(context.Background()).
			WithProjectID(id),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("list multi-machine jobs returned empty payload")
	}
	var result []*MMT
	for _, model := range resp.Payload.MultiMachineJobs {
		if model == nil {
			continue
		}
		result = append(result, t.mmtFromModel(model))
	}
	return result, nil
}

// Secrets returns redacted secret names for the teamspace.
func (t *Teamspace) Secrets() (map[string]string, error) {
	secrets, err := t.listSecrets()
	if err != nil {
		return nil, err
	}
	return redactedSecrets(secrets), nil
}

// SetSecret creates or updates a teamspace secret.
func (t *Teamspace) SetSecret(key, value string) error {
	if !validSecretName(key) {
		return errors.New("secret keys must only contain alphanumeric characters and underscores and not begin with a number")
	}
	id, err := t.requireID("set secret")
	if err != nil {
		return err
	}
	secrets, err := t.listSecrets()
	if err != nil {
		return err
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	for _, secret := range secrets {
		if secret != nil && secret.Name == key {
			_, err := api.SecretService.SecretServiceUpdateSecret(
				secret_service.NewSecretServiceUpdateSecretParamsWithContext(context.Background()).
					WithProjectID(id).
					WithID(secret.ID).
					WithBody(&models.SecretServiceUpdateSecretBody{Value: value}),
			)
			return err
		}
	}
	secretType := models.V1SecretTypeSECRETTYPEUNSPECIFIED
	_, err = api.SecretService.SecretServiceCreateSecret(
		secret_service.NewSecretServiceCreateSecretParamsWithContext(context.Background()).
			WithProjectID(id).
			WithBody(&models.SecretServiceCreateSecretBody{Name: key, Type: &secretType, Value: value}),
	)
	return err
}

// NewFolder creates a managed folder in the teamspace.
func (t *Teamspace) NewFolder(name string, opts ...FolderOptions) error {
	id, err := t.requireID("new folder")
	if err != nil {
		return err
	}
	if name == "" {
		return errors.New("teamspace new folder requires name")
	}
	api, err := sdkclient.New()
	if err != nil {
		return err
	}
	resolved := applyFolderOptions(opts...)
	body := &models.DataConnectionServiceCreateDataConnectionBody{
		Name:            name,
		CreateResources: true,
		Force:           true,
		Writable:        true,
	}
	switch resolved.location {
	case "", FolderLocationCloudAgnostic:
		body.R2 = &models.V1R2DataConnection{Name: name}
	case FolderLocationAWS:
		cloudAccount := firstNonEmpty(resolved.cloud, t.DefaultCloudAccount())
		if cloudAccount == "" {
			return errors.New("teamspace AWS folder requires cloud account")
		}
		body.ClusterID = cloudAccount
		body.AccessClusterIds = []string{cloudAccount}
		body.S3Folder = &models.V1S3FolderDataConnection{}
	case FolderLocationGCP:
		cloudAccount := firstNonEmpty(resolved.cloud, t.DefaultCloudAccount())
		if cloudAccount == "" {
			return errors.New("teamspace GCP folder requires cloud account")
		}
		body.ClusterID = cloudAccount
		body.AccessClusterIds = []string{cloudAccount}
		body.GcsFolder = &models.V1GCSFolderDataConnection{}
	default:
		return fmt.Errorf("unsupported teamspace folder location: %s", resolved.location)
	}
	_, err = api.DataConnectionService.DataConnectionServiceCreateDataConnection(
		data_connection_service.NewDataConnectionServiceCreateDataConnectionParamsWithContext(context.Background()).
			WithProjectID(id).
			WithBody(body),
	)
	return err
}

// NewConnection creates a teamspace data connection.
func (t *Teamspace) NewConnection(name, source string, connectionType ConnectionType, opts ...ConnectionOptions) error {
	id, err := t.requireID("new connection")
	if err != nil {
		return err
	}
	if name == "" {
		return errors.New("teamspace new connection requires name")
	}
	if source == "" {
		return errors.New("teamspace new connection requires source")
	}
	if connectionType != ConnectionTypeEFS {
		return fmt.Errorf("teamspace new connection only supports %s connections", ConnectionTypeEFS)
	}
	resolved := applyConnectionOptions(opts...)
	if resolved.region == "" {
		return errors.New("teamspace new EFS connection requires region")
	}
	cloudAccount := firstNonEmpty(resolved.cloud, t.DefaultCloudAccount())
	if cloudAccount == "" {
		return errors.New("teamspace new connection requires cloud account")
	}
	api, err := sdkclient.NewRaw()
	if err != nil {
		return err
	}
	body := map[string]any{
		"name":             name,
		"createResources":  false,
		"force":            true,
		"writable":         resolved.writable,
		"clusterId":        cloudAccount,
		"accessClusterIds": []string{cloudAccount},
		"efs": map[string]any{
			"fileSystemId": source,
			"region":       resolved.region,
		},
	}
	return api.Do(context.Background(), http.MethodPost, teamspaceDataConnectionPath(id), nil, body, nil)
}

// DownloadFile downloads a teamspace artifact file.
func (t *Teamspace) DownloadFile(remotePath, filePath string, cloudAccount ...string) error {
	id, err := t.requireID("download file")
	if err != nil {
		return err
	}
	if remotePath == "" {
		return errors.New("teamspace download file requires remote path")
	}
	if filePath == "" {
		filePath = remotePath
	}
	api, err := sdkclient.NewRaw()
	if err != nil {
		return err
	}
	query := url.Values{}
	if len(cloudAccount) > 0 && cloudAccount[0] != "" {
		query.Set("clusterId", cloudAccount[0])
	}
	if token := os.Getenv("LIGHTNING_AUTH_TOKEN"); token != "" {
		query.Set("token", token)
	}
	return api.Download(context.Background(), teamspaceArtifactBlobPath(id, remotePath), query, filePath)
}

// DownloadFolder downloads a teamspace artifact folder.
func (t *Teamspace) DownloadFolder(remotePath, targetPath string, cloudAccount ...string) error {
	id, err := t.requireID("download folder")
	if err != nil {
		return err
	}
	if remotePath == "" {
		return errors.New("teamspace download folder requires remote path")
	}
	if targetPath == "" {
		targetPath = remotePath
	}
	api, err := sdkclient.NewRaw()
	if err != nil {
		return err
	}
	remotePath = strings.Trim(remotePath, "/")
	treeQuery := teamspaceArtifactQuery(cloudAccount...)
	treeQuery.Set("recursive", "true")
	var tree artifactTreeResponse
	if err := api.Do(context.Background(), http.MethodGet, teamspaceArtifactTreePath(id, remotePath), treeQuery, nil, &tree); err != nil {
		return err
	}
	downloadQuery := teamspaceArtifactQuery(cloudAccount...)
	for _, item := range tree.Tree {
		if item.Type != "blob" || item.Path == "" {
			continue
		}
		remoteFilePath := strings.TrimLeft(item.Path, "/")
		if remotePath != "" {
			remoteFilePath = remotePath + "/" + remoteFilePath
		}
		targetFilePath := filepath.Join(targetPath, filepath.FromSlash(item.Path))
		if err := api.Download(context.Background(), teamspaceArtifactBlobPath(id, remoteFilePath), downloadQuery, targetFilePath); err != nil {
			return err
		}
	}
	return nil
}

// UploadFile uploads a file into teamspace artifacts.
func (t *Teamspace) UploadFile(filePath, remotePath string, cloudAccount ...string) error {
	id, err := t.requireID("upload file")
	if err != nil {
		return err
	}
	if filePath == "" {
		return errors.New("teamspace upload file requires file path")
	}
	if remotePath == "" {
		remotePath = filepath.Base(filePath)
	}
	api, err := sdkclient.NewRaw()
	if err != nil {
		return err
	}
	query := url.Values{}
	if len(cloudAccount) > 0 && cloudAccount[0] != "" {
		query.Set("clusterId", cloudAccount[0])
	}
	if token := os.Getenv("LIGHTNING_AUTH_TOKEN"); token != "" {
		query.Set("token", token)
	}
	return api.Upload(context.Background(), teamspaceArtifactBlobPath(id, remotePath), query, filePath, false)
}

// UploadFolder uploads all files from a local folder into teamspace artifacts.
func (t *Teamspace) UploadFolder(folderPath, remotePath string, cloudAccount ...string) error {
	if _, err := t.requireID("upload folder"); err != nil {
		return err
	}
	if folderPath == "" {
		return errors.New("teamspace upload folder requires folder path")
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
		if err := t.UploadFile(filePath, remoteFilePath, cloudAccount...); err != nil {
			return err
		}
	}
	return nil
}

func (t *Teamspace) listSecrets() ([]*models.V1Secret, error) {
	id, err := t.requireID("secrets")
	if err != nil {
		return nil, err
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	resp, err := api.SecretService.SecretServiceListSecrets(
		secret_service.NewSecretServiceListSecretsParamsWithContext(context.Background()).
			WithProjectID(id),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("list teamspace secrets returned empty payload")
	}
	return resp.Payload.Secrets, nil
}

func applyTeamspaceOptions(opts ...TeamspaceOptions) teamspaceOptions {
	var resolved teamspaceOptions
	if len(opts) > 0 {
		resolved.id = opts[0].ID
		resolved.owner = opts[0].Owner
		resolved.defaultCloudAccount = opts[0].DefaultCloudAccount
		resolved.startStudiosOnInterruptible = opts[0].StartStudiosOnInterruptible
		if resolved.owner != nil {
			resolved.ownerID = resolved.owner.ID()
			resolved.ownerName = resolved.owner.Name()
		}
	}
	return resolved
}

func applyConnectionOptions(opts ...ConnectionOptions) connectionOptions {
	resolved := connectionOptions{writable: true}
	if len(opts) > 0 {
		resolved.cloud = opts[0].Cloud
		resolved.region = opts[0].Region
		if opts[0].Writable != nil {
			resolved.writable = *opts[0].Writable
		}
	}
	return resolved
}

func applyFolderOptions(opts ...FolderOptions) folderOptions {
	var resolved folderOptions
	if len(opts) > 0 {
		resolved.cloud = opts[0].Cloud
		resolved.location = opts[0].Location
	}
	return resolved
}

func resolveTeamspaceOwner(api *sdkapi.LightningSdkAPI, opts teamspaceOptions) (string, string, error) {
	if opts.ownerID != "" {
		return opts.ownerID, opts.ownerName, nil
	}
	return "", "", errors.New("teamspace requires owner or ID")
}

func (t *Teamspace) machineCloudAccounts(cloud string) ([]string, string, error) {
	if cloud == "" {
		accounts, err := t.cloudAccountIDs()
		if err != nil {
			return nil, "", err
		}
		return nonEmptyStrings(accounts), "", nil
	}
	if isCloudProvider(cloud) {
		accounts, err := t.cloudAccountIDs()
		if err != nil {
			return nil, "", err
		}
		return nonEmptyStrings(accounts), normalizeCloudProvider(cloud), nil
	}
	return []string{cloud}, "", nil
}

func (t *Teamspace) cloudAccountIDs() ([]string, error) {
	accounts, err := t.boundCloudAccounts()
	if err != nil {
		return nil, err
	}
	var result []string
	for _, account := range accounts {
		if account.id != "" {
			result = append(result, account.id)
		}
	}
	return result, nil
}

type boundCloudAccount struct {
	id   string
	name string
}

func (t *Teamspace) boundCloudAccounts() ([]boundCloudAccount, error) {
	id, err := t.requireID("cloud accounts")
	if err != nil {
		return nil, err
	}
	api, err := sdkclient.New()
	if err != nil {
		return nil, err
	}
	resp, err := api.ProjectsService.ProjectsServiceListProjectClusterBindings(
		projects_service.NewProjectsServiceListProjectClusterBindingsParamsWithContext(context.Background()).
			WithProjectID(id),
	)
	if err != nil {
		return nil, err
	}
	if resp.Payload == nil {
		return nil, fmt.Errorf("list teamspace cloud accounts returned empty payload")
	}
	var result []boundCloudAccount
	for _, cluster := range resp.Payload.Clusters {
		if cluster == nil {
			continue
		}
		result = append(result, boundCloudAccount{id: cluster.ClusterID, name: cluster.ClusterName})
	}
	return result, nil
}

func nonEmptyStrings(values []string) []string {
	var result []string
	for _, value := range values {
		if value != "" {
			result = append(result, value)
		}
	}
	return result
}

func (t *Teamspace) jobFromModel(model *models.V1Job) *Job {
	if model == nil {
		return nil
	}
	opts := JobOptions{
		ID:        model.ID,
		Teamspace: t,
		Status:    model.State,
		PublicIP:  model.PublicIPAddress,
		TotalCost: model.TotalCost,
	}
	if model.Spec != nil {
		opts.Machine = Machine(model.Spec.InstanceName)
		opts.Command = model.Spec.Command
		opts.Image = model.Spec.Image
	}
	result := jobFromModel(model, applyJobOptions(opts))
	if result != nil && model.Spec != nil {
		result.studioID = model.Spec.CloudspaceID
	}
	return result
}

func (t *Teamspace) mmtFromModel(model *models.V1MultiMachineJob) *MMT {
	if model == nil {
		return nil
	}
	opts := MMTOptions{
		ID:          model.ID,
		Teamspace:   t,
		NumMachines: model.Machines,
		TotalCost:   model.TotalCost,
	}
	if model.State != nil {
		opts.Status = string(*model.State)
	}
	if model.Spec != nil {
		opts.Machine = Machine(model.Spec.InstanceName)
		opts.Command = model.Spec.Command
		opts.Image = model.Spec.Image
	}
	result := mmtFromModel(model, applyMMTOptions(opts))
	if result != nil {
		result.studioID = model.CloudspaceID
		if result.studioID == "" && model.Spec != nil {
			result.studioID = model.Spec.CloudspaceID
		}
	}
	return result
}

func teamspaceArtifactBlobPath(teamspaceID, remotePath string) string {
	return "/v1/projects/" + url.PathEscape(teamspaceID) + "/artifacts/blobs/" + strings.TrimLeft(remotePath, "/")
}

func teamspaceArtifactTreePath(teamspaceID, remotePath string) string {
	return "/v1/projects/" + url.PathEscape(teamspaceID) + "/artifacts/trees/" + strings.TrimLeft(remotePath, "/")
}

func teamspaceDataConnectionPath(teamspaceID string) string {
	return "/v1/projects/" + url.PathEscape(teamspaceID) + "/data-connections"
}

func teamspaceArtifactQuery(cloudAccount ...string) url.Values {
	query := url.Values{}
	if len(cloudAccount) > 0 && cloudAccount[0] != "" {
		query.Set("clusterId", cloudAccount[0])
	}
	if token := os.Getenv("LIGHTNING_AUTH_TOKEN"); token != "" {
		query.Set("token", token)
	}
	return query
}

func applyProjectSettings(t *Teamspace, project *models.V1Project) {
	if project.ProjectSettings == nil {
		return
	}
	t.defaultCloudAccount = project.ProjectSettings.PreferredCluster
	t.startStudiosOnInterruptible = project.ProjectSettings.StartStudioOnSpotInstance
}
