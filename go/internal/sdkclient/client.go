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

func (c *RawClient) Upload(ctx context.Context, requestPath string, query url.Values, sourcePath string, notifyCompletion bool) error {
	file, err := os.Open(sourcePath)
	if err != nil {
		return err
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPut, c.url(requestPath, query), file)
	if err != nil {
		return err
	}
	req.ContentLength = info.Size()
	req.GetBody = func() (io.ReadCloser, error) {
		return os.Open(sourcePath)
	}
	setRequestAuth(req, c.auth)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	if err := closeUploadResponse(resp, http.StatusOK, requestPath); err != nil {
		return err
	}
	if !notifyCompletion {
		return nil
	}
	completePath := strings.TrimRight(requestPath, "/") + "/complete"
	completeReq, err := http.NewRequestWithContext(ctx, http.MethodPost, c.url(completePath, query), nil)
	if err != nil {
		return err
	}
	setRequestAuth(completeReq, c.auth)
	completeResp, err := c.httpClient.Do(completeReq)
	if err != nil {
		return err
	}
	if completeResp.StatusCode == http.StatusOK || completeResp.StatusCode == http.StatusNoContent {
		_, _ = io.Copy(io.Discard, completeResp.Body)
		return completeResp.Body.Close()
	}
	return closeUploadResponse(completeResp, http.StatusOK, completePath)
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
