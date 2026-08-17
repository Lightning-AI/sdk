package lit

import (
	"context"
	"errors"
	"net/http"
	"net/url"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/models"
	"github.com/lightning-ai/sdk/go/internal/sdkclient"
)

var secretNamePattern = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

type artifactTreeResponse struct {
	Tree []artifactTreeItem `json:"tree"`
	// NextCursor resumes the listing at the next page, as the "cursor"
	// query parameter. Empty means this was the last page.
	NextCursor string `json:"nextCursor"`
}

type artifactTreeItem struct {
	Path         string `json:"path"`
	Type         string `json:"type"`
	Size         int64  `json:"size"`
	ClusterID    string `json:"clusterId"`
	LastModified string `json:"lastModified"`
}

// FileEntry is one entry of a drive folder listing.
type FileEntry struct {
	// Path is relative to the listed folder.
	Path string
	// Type is "blob" for a file or "tree" for a folder.
	Type string
	// Size in bytes; zero for folders.
	Size int64
	// CloudAccount is the storage cluster holding a file, when reported.
	CloudAccount string
	// LastModified is the file's RFC 3339 modification time, when reported.
	LastModified string
}

// listArtifactFolder lists every entry under treePath, following the
// listing's cursor pages. query gains the cursor between pages.
func listArtifactFolder(api *sdkclient.RawClient, treePath string, query url.Values) ([]FileEntry, error) {
	var entries []FileEntry
	for {
		var tree artifactTreeResponse
		if err := api.Do(context.Background(), http.MethodGet, treePath, query, nil, &tree); err != nil {
			return nil, err
		}
		for _, item := range tree.Tree {
			entries = append(entries, FileEntry{
				Path:         item.Path,
				Type:         item.Type,
				Size:         item.Size,
				CloudAccount: item.ClusterID,
				LastModified: item.LastModified,
			})
		}
		if tree.NextCursor == "" {
			return entries, nil
		}
		if query == nil {
			query = url.Values{}
		}
		query.Set("cursor", tree.NextCursor)
	}
}

// downloadArtifactFolder downloads every file listed under treePath into
// targetPath, following the listing's cursor pages. blobPath maps a listed
// file's remote path to its blobs route. treeQuery gains the cursor between
// pages; downloadQuery rides along on every file download.
func downloadArtifactFolder(
	api *sdkclient.RawClient,
	remotePath, targetPath, treePath string,
	blobPath func(remoteFilePath string) string,
	treeQuery, downloadQuery url.Values,
) error {
	for {
		var tree artifactTreeResponse
		if err := api.Do(context.Background(), http.MethodGet, treePath, treeQuery, nil, &tree); err != nil {
			return err
		}
		for _, item := range tree.Tree {
			if item.Type != "blob" || item.Path == "" {
				continue
			}
			remoteFilePath := strings.TrimLeft(item.Path, "/")
			if remotePath != "" {
				remoteFilePath = remotePath + "/" + remoteFilePath
			}
			targetFilePath := filepath.Join(targetPath, filepath.FromSlash(item.Path))
			if err := api.Download(context.Background(), blobPath(remoteFilePath), downloadQuery, targetFilePath); err != nil {
				return err
			}
		}
		if tree.NextCursor == "" {
			return nil
		}
		treeQuery.Set("cursor", tree.NextCursor)
	}
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}

func cloneMap(values map[string]string) map[string]string {
	if values == nil {
		return nil
	}
	result := make(map[string]string, len(values))
	for key, value := range values {
		result[key] = value
	}
	return result
}

func envVars(env map[string]string) []*models.V1EnvVar {
	if len(env) == 0 {
		return nil
	}
	var result []*models.V1EnvVar
	for key, value := range env {
		result = append(result, &models.V1EnvVar{Name: key, Value: value})
	}
	return result
}

func cloudSpaceState(cloudspace *models.V1CloudSpace) string {
	if cloudspace.State == nil {
		return ""
	}
	return string(*cloudspace.State)
}

func ownerTeamspace(ownerName, teamspaceName string) string {
	if ownerName == "" {
		return teamspaceName
	}
	if teamspaceName == "" {
		return ownerName
	}
	return ownerName + "/" + teamspaceName
}

func maxRuntime(seconds int) string {
	if seconds <= 0 {
		return ""
	}
	return strconv.Itoa(seconds)
}

func resolveEntrypoint(command string, entrypoint *string, image string) string {
	if entrypoint != nil {
		return *entrypoint
	}
	if image != "" && command != "" {
		return "sh -c"
	}
	return ""
}

func artifactConnection(destination string) (string, string) {
	parts := strings.Split(destination, ":")
	if len(parts) == 2 {
		return parts[1], ""
	}
	if len(parts) == 3 {
		return parts[1], parts[2]
	}
	return "", ""
}

func validateArtifacts(source, destination string) error {
	if source == "" && destination == "" {
		return nil
	}
	if source == "" || destination == "" {
		return errors.New("artifacts require both local and remote paths")
	}
	parts := strings.Split(destination, ":")
	if len(parts) != 2 && len(parts) != 3 {
		return errors.New("artifact remote path must be <CONNECTION_TYPE>:<CONNECTION_NAME>[:PATH_WITHIN_CONNECTION]")
	}
	return nil
}

func validSecretName(name string) bool {
	return secretNamePattern.MatchString(name)
}

func isGenericSecret(secret *models.V1Secret) bool {
	return secret != nil &&
		(secret.Type == nil || *secret.Type == models.V1SecretTypeSECRETTYPEUNSPECIFIED)
}

func redactedSecrets(secrets []*models.V1Secret) map[string]string {
	result := map[string]string{}
	for _, secret := range secrets {
		if !isGenericSecret(secret) {
			continue
		}
		result[secret.Name] = "***REDACTED***"
	}
	return result
}
