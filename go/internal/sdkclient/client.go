package sdkclient

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	retry "github.com/avast/retry-go/v4"
	httptransport "github.com/go-openapi/runtime/client"
	"github.com/go-openapi/strfmt"

	"github.com/lightning-ai/sdk/go/internal/lightningcloud/openapi/generated/client"
)

const (
	defaultBaseURL = "https://lightning.ai"
	defaultRetries = 7
)

func New() (*client.LightningSdkAPI, error) {
	parsed, err := baseURL()
	if err != nil {
		return nil, err
	}
	auth, err := resolveAuth()
	if err != nil {
		return nil, err
	}
	basePath := strings.TrimRight(parsed.Path, "/")
	if basePath == "" {
		basePath = "/"
	}
	transport := httptransport.New(parsed.Host, basePath, []string{parsed.Scheme})
	transport.Transport = retryTransport{base: http.DefaultTransport, maxTries: defaultRetries}
	setGeneratedAuth(transport, auth)

	return client.New(transport, strfmt.Default), nil
}

type RawClient struct {
	baseURL    *url.URL
	httpClient *http.Client
	auth       authCredentials
}

func NewRaw() (*RawClient, error) {
	parsed, err := baseURL()
	if err != nil {
		return nil, err
	}
	auth, err := resolveAuth()
	if err != nil {
		return nil, err
	}
	return &RawClient{
		baseURL: parsed,
		httpClient: &http.Client{
			Transport: retryTransport{base: http.DefaultTransport, maxTries: defaultRetries},
		},
		auth: auth,
	}, nil
}

func (c *RawClient) Do(ctx context.Context, method, requestPath string, query url.Values, body any, out any) error {
	var bodyReader io.Reader
	if body != nil {
		var buf bytes.Buffer
		if err := json.NewEncoder(&buf).Encode(body); err != nil {
			return err
		}
		bodyReader = &buf
	}
	req, err := http.NewRequestWithContext(ctx, method, c.url(requestPath, query), bodyReader)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	setRequestAuth(req, c.auth)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		message, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("%s %s returned %s: %s", method, requestPath, resp.Status, strings.TrimSpace(string(message)))
	}
	if out == nil {
		_, _ = io.Copy(io.Discard, resp.Body)
		return nil
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

func (c *RawClient) Download(ctx context.Context, requestPath string, query url.Values, targetPath string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.url(requestPath, query), nil)
	if err != nil {
		return err
	}
	setRequestAuth(req, c.auth)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		message, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("GET %s returned %s: %s", requestPath, resp.Status, strings.TrimSpace(string(message)))
	}
	if dir := filepath.Dir(targetPath); dir != "." && dir != "" {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	file, err := os.Create(targetPath)
	if err != nil {
		return err
	}
	defer file.Close()
	_, err = io.Copy(file, resp.Body)
	return err
}

// UploadOptions configures RawClient.Upload.
type UploadOptions struct {
	// ClusterID is the cluster to store the blob on; required for teamspace
	// uploads, ignored by the studio scope.
	ClusterID string
	// NotifyCompletion finalizes the upload via {scope}/blobs/complete after
	// the PUT; the studio scope needs it so the file shows up in a running
	// Studio.
	NotifyCompletion bool
}

type blobUploadBlob struct {
	Path string `json:"path"`
}

type blobUploadBatch struct {
	ClusterID string           `json:"cluster_id,omitempty"`
	Blobs     []blobUploadBlob `json:"blobs"`
}

// blobUploadURL is one presigned URL returned by the blob-upload route, with
// any headers that must be replayed so the request matches the signature.
type blobUploadURL struct {
	URL     string            `json:"url"`
	Headers map[string]string `json:"headers,omitempty"`
}

type blobUploadResult struct {
	Path string          `json:"path"`
	URLs []blobUploadURL `json:"urls"`
}

type blobUploadResponse struct {
	Results []blobUploadResult `json:"results"`
}

const (
	// signedPutAttempts bounds the fresh-URL retries of the storage PUT.
	signedPutAttempts = 7
	// signedPutBaseDelay is the first retry delay; it doubles per attempt.
	signedPutBaseDelay = 500 * time.Millisecond
)

// storagePutClient sends the presigned storage PUTs. It deliberately skips the
// retrying transport: a rejected signed URL should be re-signed, not replayed.
var storagePutClient = &http.Client{}

// Upload sends sourcePath to blobPath within the upload scope rooted at
// scopePath (e.g. /v1/projects/{id}/artifacts): it requests a presigned URL
// from POST {scopePath}/blobs, PUTs the file bytes straight to storage, and
// finalizes via POST {scopePath}/blobs/complete when requested.
//
// Every attempt PUTs to a freshly signed URL, so retries heal expired
// signatures, transient storage errors, and newly issued storage credentials
// that haven't propagated yet (e.g. right after a managed folder is created).
func (c *RawClient) Upload(ctx context.Context, scopePath, blobPath string, query url.Values, sourcePath string, opts UploadOptions) error {
	batch := blobUploadBatch{
		ClusterID: opts.ClusterID,
		Blobs:     []blobUploadBlob{{Path: blobPath}},
	}
	uploadPath := strings.TrimRight(scopePath, "/") + "/blobs"

	var err error
	for attempt := 1; attempt <= signedPutAttempts; attempt++ {
		if attempt > 1 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(signedPutBaseDelay << (attempt - 2)):
			}
		}
		var signed blobUploadURL
		signed, err = c.requestUploadURL(ctx, uploadPath, query, batch, blobPath)
		if err != nil {
			return err
		}
		var retryable bool
		retryable, err = putFileToSignedURL(ctx, signed, sourcePath, blobPath)
		if err == nil {
			break
		}
		if !retryable {
			return err
		}
	}
	if err != nil {
		return err
	}

	if !opts.NotifyCompletion {
		return nil
	}
	return c.Do(ctx, http.MethodPost, uploadPath+"/complete", query, batch, nil)
}

func (c *RawClient) requestUploadURL(ctx context.Context, uploadPath string, query url.Values, batch blobUploadBatch, blobPath string) (blobUploadURL, error) {
	var created blobUploadResponse
	if err := c.Do(ctx, http.MethodPost, uploadPath, query, batch, &created); err != nil {
		return blobUploadURL{}, err
	}
	if len(created.Results) != 1 || len(created.Results[0].URLs) != 1 {
		return blobUploadURL{}, fmt.Errorf("POST %s returned no upload URL for %q", uploadPath, blobPath)
	}
	return created.Results[0].URLs[0], nil
}

// putFileToSignedURL PUTs the file to the presigned URL, reporting whether a
// failure is worth retrying with a freshly signed URL: transport errors,
// throttling, server errors, and 401/403 (storage may not honor just-issued
// credentials yet, and signatures expire).
func putFileToSignedURL(ctx context.Context, signed blobUploadURL, sourcePath, blobPath string) (retryable bool, err error) {
	file, err := os.Open(sourcePath)
	if err != nil {
		return false, err
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return false, err
	}
	// An empty file must go out as http.NoBody: a zero ContentLength with a
	// non-nil body is treated as unknown length and sent chunked, which
	// storage providers reject on presigned PUTs.
	var body io.Reader = file
	if info.Size() == 0 {
		body = http.NoBody
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPut, signed.URL, body)
	if err != nil {
		return false, err
	}
	req.ContentLength = info.Size()
	// The presigned URL carries its own authentication; extra credentials
	// would invalidate the signature.
	for name, value := range signed.Headers {
		req.Header.Set(name, value)
	}
	resp, err := storagePutClient.Do(req)
	if err != nil {
		return true, err
	}
	retryable = resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden ||
		resp.StatusCode == http.StatusTooManyRequests || resp.StatusCode >= 500
	return retryable, closeUploadResponse(resp, http.StatusOK, blobPath)
}

func (c *RawClient) url(requestPath string, query url.Values) string {
	resolved := *c.baseURL
	basePath := strings.TrimRight(resolved.Path, "/")
	if basePath == "" || basePath == "/" {
		resolved.Path = "/" + strings.TrimLeft(requestPath, "/")
	} else {
		resolved.Path = basePath + "/" + strings.TrimLeft(requestPath, "/")
	}
	resolved.RawQuery = query.Encode()
	return resolved.String()
}

func closeUploadResponse(resp *http.Response, expectedStatus int, requestPath string) error {
	defer resp.Body.Close()
	if resp.StatusCode != expectedStatus {
		message, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("%s returned %s: %s", requestPath, resp.Status, strings.TrimSpace(string(message)))
	}
	_, _ = io.Copy(io.Discard, resp.Body)
	return nil
}

func baseURL() (*url.URL, error) {
	baseURL := os.Getenv("LIGHTNING_CLOUD_URL")
	if baseURL == "" {
		baseURL = os.Getenv("GRID_URL")
	}
	if baseURL == "" {
		baseURL = defaultBaseURL
	}

	return url.Parse(baseURL)
}

type authKind int

const (
	authNone authKind = iota
	authBearer
	authBasic
)

type authCredentials struct {
	kind   authKind
	token  string
	userID string
	apiKey string
}

type credentialsFile struct {
	UserID    string `json:"user_id"`
	APIKey    string `json:"api_key"`
	AuthToken string `json:"auth_token"`
}

func resolveAuth() (authCredentials, error) {
	if authToken := os.Getenv("LIGHTNING_AUTH_TOKEN"); authToken != "" {
		return authCredentials{kind: authBearer, token: authToken}, nil
	}
	if userID, apiKey := os.Getenv("LIGHTNING_USER_ID"), os.Getenv("LIGHTNING_API_KEY"); userID != "" && apiKey != "" {
		return authCredentials{kind: authBasic, userID: userID, apiKey: apiKey}, nil
	}
	credentials, ok, err := loadCredentialsFile()
	if err != nil || !ok {
		return authCredentials{}, err
	}
	if credentials.AuthToken != "" {
		return authCredentials{kind: authBearer, token: credentials.AuthToken}, nil
	}
	if credentials.UserID != "" && credentials.APIKey != "" {
		return authCredentials{kind: authBasic, userID: credentials.UserID, apiKey: credentials.APIKey}, nil
	}
	return authCredentials{}, nil
}

func loadCredentialsFile() (credentialsFile, bool, error) {
	path, ok := credentialsPath()
	if !ok {
		return credentialsFile{}, false, nil
	}
	file, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) {
		return credentialsFile{}, false, nil
	}
	if err != nil {
		return credentialsFile{}, false, err
	}
	defer file.Close()
	var credentials credentialsFile
	if err := json.NewDecoder(file).Decode(&credentials); err != nil {
		return credentialsFile{}, false, err
	}
	return credentials, true, nil
}

func credentialsPath() (string, bool) {
	if path := os.Getenv("LIGHTNING_CREDENTIAL_PATH"); path != "" {
		return path, true
	}
	home, err := os.UserHomeDir()
	if err != nil || home == "" {
		return "", false
	}
	return filepath.Join(home, ".lightning", "credentials.json"), true
}

func setGeneratedAuth(transport *httptransport.Runtime, auth authCredentials) {
	switch auth.kind {
	case authBearer:
		transport.DefaultAuthentication = httptransport.BearerToken(auth.token)
	case authBasic:
		transport.DefaultAuthentication = httptransport.BasicAuth(auth.userID, auth.apiKey)
	}
}

func setRequestAuth(req *http.Request, auth authCredentials) {
	switch auth.kind {
	case authBearer:
		req.Header.Set("Authorization", "Bearer "+auth.token)
	case authBasic:
		req.SetBasicAuth(auth.userID, auth.apiKey)
	}
}

type retryTransport struct {
	base     http.RoundTripper
	maxTries int
}

type retryableStatusError struct {
	statusCode int
}

func (e retryableStatusError) Error() string {
	return fmt.Sprintf("retryable HTTP status %d", e.statusCode)
}

func (rt retryTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	base := rt.base
	if base == nil {
		base = http.DefaultTransport
	}
	tries := rt.maxTries
	if tries <= 0 {
		tries = 1
	}

	var resp *http.Response
	attempt := 0
	err := retry.Do(
		func() error {
			attempt++
			retryReq, err := requestForRetry(req)
			if err != nil {
				return retry.Unrecoverable(err)
			}
			currentResp, err := base.RoundTrip(retryReq)
			if err != nil {
				return err
			}
			if !shouldRetry(currentResp.StatusCode) {
				resp = currentResp
				return nil
			}
			if attempt < tries && currentResp.Body != nil {
				_ = currentResp.Body.Close()
			}
			resp = currentResp
			return retryableStatusError{statusCode: currentResp.StatusCode}
		},
		retry.Attempts(uint(tries)),
		retry.Context(req.Context()),
		retry.Delay(500*time.Millisecond),
		retry.DelayType(retry.BackOffDelay),
		retry.MaxDelay(5*time.Minute),
		retry.LastErrorOnly(true),
	)
	if resp != nil {
		return resp, nil
	}
	return nil, err
}

func requestForRetry(req *http.Request) (*http.Request, error) {
	retryReq := req.Clone(req.Context())
	if req.Body != nil && req.GetBody != nil {
		body, err := req.GetBody()
		if err != nil {
			return nil, err
		}
		retryReq.Body = body
	}
	return retryReq, nil
}

func shouldRetry(statusCode int) bool {
	if statusCode >= 500 {
		return true
	}
	return statusCode >= 400 && statusCode < 500 && statusCode != 400 && statusCode != 401 && statusCode != 404
}
