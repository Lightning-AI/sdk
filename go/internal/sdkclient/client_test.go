package sdkclient

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req)
}

func TestRetryTransportRetriesRetryableStatus(t *testing.T) {
	attempts := 0
	transport := retryTransport{
		maxTries: 2,
		base: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			attempts++
			if attempts == 1 {
				return response(http.StatusInternalServerError, "try again"), nil
			}
			return response(http.StatusOK, "ok"), nil
		}),
	}
	req := request(t, http.MethodGet, nil)

	resp, err := transport.RoundTrip(req)
	if err != nil {
		t.Fatalf("RoundTrip returned error: %v", err)
	}
	defer resp.Body.Close()
	if attempts != 2 {
		t.Fatalf("attempts = %d, want 2", attempts)
	}
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want %d", resp.StatusCode, http.StatusOK)
	}
}

func TestRetryTransportDoesNotRetryNonRetryableStatus(t *testing.T) {
	attempts := 0
	transport := retryTransport{
		maxTries: 2,
		base: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			attempts++
			return response(http.StatusBadRequest, "bad request"), nil
		}),
	}
	req := request(t, http.MethodGet, nil)

	resp, err := transport.RoundTrip(req)
	if err != nil {
		t.Fatalf("RoundTrip returned error: %v", err)
	}
	defer resp.Body.Close()
	if attempts != 1 {
		t.Fatalf("attempts = %d, want 1", attempts)
	}
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", resp.StatusCode, http.StatusBadRequest)
	}
}

func TestRetryTransportReplaysRequestBody(t *testing.T) {
	attempts := 0
	transport := retryTransport{
		maxTries: 2,
		base: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			attempts++
			body, err := io.ReadAll(req.Body)
			if err != nil {
				t.Fatalf("read body: %v", err)
			}
			if string(body) != "payload" {
				t.Fatalf("attempt %d body = %q, want payload", attempts, string(body))
			}
			if attempts == 1 {
				return response(http.StatusTooManyRequests, "try again"), nil
			}
			return response(http.StatusOK, "ok"), nil
		}),
	}
	req := request(t, http.MethodPost, strings.NewReader("payload"))

	resp, err := transport.RoundTrip(req)
	if err != nil {
		t.Fatalf("RoundTrip returned error: %v", err)
	}
	defer resp.Body.Close()
	if attempts != 2 {
		t.Fatalf("attempts = %d, want 2", attempts)
	}
}

func TestRetryTransportReturnsFinalRetryableResponse(t *testing.T) {
	attempts := 0
	transport := retryTransport{
		maxTries: 2,
		base: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			attempts++
			return response(http.StatusServiceUnavailable, "final body"), nil
		}),
	}
	req := request(t, http.MethodGet, nil)

	resp, err := transport.RoundTrip(req)
	if err != nil {
		t.Fatalf("RoundTrip returned error: %v", err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read final body: %v", err)
	}
	if attempts != 2 {
		t.Fatalf("attempts = %d, want 2", attempts)
	}
	if resp.StatusCode != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want %d", resp.StatusCode, http.StatusServiceUnavailable)
	}
	if string(body) != "final body" {
		t.Fatalf("body = %q, want final body", string(body))
	}
}

func TestResolveAuthPrefersEnvBearer(t *testing.T) {
	resetAuthEnv(t)
	t.Setenv("LIGHTNING_AUTH_TOKEN", "env-token")
	t.Setenv("LIGHTNING_USER_ID", "env-user")
	t.Setenv("LIGHTNING_API_KEY", "env-key")
	writeCredentialsFile(t, `{"auth_token":"file-token","user_id":"file-user","api_key":"file-key"}`)

	auth, err := resolveAuth()
	if err != nil {
		t.Fatalf("resolveAuth returned error: %v", err)
	}
	if auth.kind != authBearer || auth.token != "env-token" {
		t.Fatalf("auth = %+v, want env bearer", auth)
	}
}

func TestResolveAuthUsesEnvBasic(t *testing.T) {
	resetAuthEnv(t)
	t.Setenv("LIGHTNING_USER_ID", "env-user")
	t.Setenv("LIGHTNING_API_KEY", "env-key")
	writeCredentialsFile(t, `{"auth_token":"file-token"}`)

	auth, err := resolveAuth()
	if err != nil {
		t.Fatalf("resolveAuth returned error: %v", err)
	}
	if auth.kind != authBasic || auth.userID != "env-user" || auth.apiKey != "env-key" {
		t.Fatalf("auth = %+v, want env basic", auth)
	}
}

func TestResolveAuthLoadsCredentialsFileBearer(t *testing.T) {
	resetAuthEnv(t)
	writeCredentialsFile(t, `{"auth_token":"file-token","user_id":"file-user","api_key":"file-key"}`)

	auth, err := resolveAuth()
	if err != nil {
		t.Fatalf("resolveAuth returned error: %v", err)
	}
	if auth.kind != authBearer || auth.token != "file-token" {
		t.Fatalf("auth = %+v, want file bearer", auth)
	}
}

func TestResolveAuthLoadsCredentialsFileBasic(t *testing.T) {
	resetAuthEnv(t)
	writeCredentialsFile(t, `{"user_id":"file-user","api_key":"file-key"}`)

	auth, err := resolveAuth()
	if err != nil {
		t.Fatalf("resolveAuth returned error: %v", err)
	}
	if auth.kind != authBasic || auth.userID != "file-user" || auth.apiKey != "file-key" {
		t.Fatalf("auth = %+v, want file basic", auth)
	}
}

func TestResolveAuthErrorsOnMalformedCredentialsFile(t *testing.T) {
	resetAuthEnv(t)
	writeCredentialsFile(t, `{bad json`)

	if _, err := resolveAuth(); err == nil {
		t.Fatal("resolveAuth returned nil error for malformed credentials file")
	}
}

func TestSetRequestAuthUsesResolvedBasicCredentials(t *testing.T) {
	req := request(t, http.MethodGet, nil)

	setRequestAuth(req, authCredentials{kind: authBasic, userID: "user-1", apiKey: "key-1"})

	user, password, ok := req.BasicAuth()
	if !ok {
		t.Fatal("request is missing basic auth")
	}
	if user != "user-1" || password != "key-1" {
		t.Fatalf("basic auth = %q %q, want user-1 key-1", user, password)
	}
}

func TestSetRequestAuthUsesResolvedBearerCredentials(t *testing.T) {
	req := request(t, http.MethodGet, nil)

	setRequestAuth(req, authCredentials{kind: authBearer, token: "token-1"})

	if got, want := req.Header.Get("Authorization"), "Bearer token-1"; got != want {
		t.Fatalf("authorization header = %q, want %q", got, want)
	}
}

func request(t *testing.T, method string, body io.Reader) *http.Request {
	t.Helper()
	req, err := http.NewRequest(method, "https://example.test", body)
	if err != nil {
		t.Fatal(err)
	}
	return req
}

func response(statusCode int, body string) *http.Response {
	return &http.Response{
		StatusCode: statusCode,
		Status:     http.StatusText(statusCode),
		Body:       io.NopCloser(strings.NewReader(body)),
		Header:     http.Header{},
	}
}

func resetAuthEnv(t *testing.T) {
	t.Helper()
	t.Setenv("LIGHTNING_AUTH_TOKEN", "")
	t.Setenv("LIGHTNING_USER_ID", "")
	t.Setenv("LIGHTNING_API_KEY", "")
	t.Setenv("HOME", t.TempDir())
	t.Setenv("LIGHTNING_CREDENTIAL_PATH", filepath.Join(t.TempDir(), "missing", "credentials.json"))
}

func writeCredentialsFile(t *testing.T, body string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "credentials.json")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("LIGHTNING_CREDENTIAL_PATH", path)
}

// newUploadTestClient builds a RawClient against a test server without retries,
// so failure-path tests fail fast instead of backing off.
func newUploadTestClient(t *testing.T, serverURL string) *RawClient {
	t.Helper()
	parsed, err := url.Parse(serverURL)
	if err != nil {
		t.Fatal(err)
	}
	return &RawClient{
		baseURL:    parsed,
		httpClient: &http.Client{Transport: retryTransport{maxTries: 1}},
	}
}

func writeUploadTestResponse(t *testing.T, w http.ResponseWriter, path, signedURL string) {
	t.Helper()
	w.Header().Set("Content-Type", "application/json")
	err := json.NewEncoder(w).Encode(map[string]any{
		"expires_at": "2026-01-01T00:00:00Z",
		"results":    []map[string]any{{"path": path, "urls": []map[string]any{{"url": signedURL}}}},
	})
	if err != nil {
		t.Error(err)
	}
}

func writeUploadTestFile(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "source.bin")
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestUploadEmptyFileSendsContentLengthZero(t *testing.T) {
	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method + " " + r.URL.Path {
		case "POST /scope/blobs":
			writeUploadTestResponse(t, w, "empty.bin", server.URL+"/signed/empty.bin")
		case "PUT /signed/empty.bin":
			// A chunked body would surface as TransferEncoding ["chunked"]
			// and ContentLength -1; presigned PUTs require a known length.
			if r.ContentLength != 0 || len(r.TransferEncoding) != 0 {
				t.Errorf("empty PUT: ContentLength = %d, TransferEncoding = %v, want 0 and none",
					r.ContentLength, r.TransferEncoding)
			}
		default:
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
			http.Error(w, "unexpected request", http.StatusBadRequest)
		}
	}))
	defer server.Close()

	c := newUploadTestClient(t, server.URL)
	err := c.Upload(context.Background(), "/scope", "empty.bin", nil, writeUploadTestFile(t, ""), UploadOptions{})
	if err != nil {
		t.Fatalf("Upload returned error: %v", err)
	}
}

func TestUploadFailsWhenNoURLReturned(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"expires_at": "2026-01-01T00:00:00Z", "results": []}`))
	}))
	defer server.Close()

	c := newUploadTestClient(t, server.URL)
	err := c.Upload(context.Background(), "/scope", "file.bin", nil, writeUploadTestFile(t, "data"), UploadOptions{})
	if err == nil || !strings.Contains(err.Error(), "returned no upload URL") {
		t.Fatalf("Upload error = %v, want a no-upload-URL error", err)
	}
}

func TestUploadSurfacesSignedPutFailure(t *testing.T) {
	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			writeUploadTestResponse(t, w, "file.bin", server.URL+"/signed/file.bin")
			return
		}
		http.Error(w, "no such key", http.StatusNotFound)
	}))
	defer server.Close()

	c := newUploadTestClient(t, server.URL)
	err := c.Upload(context.Background(), "/scope", "file.bin", nil, writeUploadTestFile(t, "data"), UploadOptions{})
	if err == nil || !strings.Contains(err.Error(), "404") {
		t.Fatalf("Upload error = %v, want the storage PUT's 404 to surface", err)
	}
}

func TestUploadResignsOnSignedPutAuthFailure(t *testing.T) {
	// Storage 401/403 must be retried with a freshly signed URL: just-issued
	// storage credentials can lag behind (e.g. right after a managed folder
	// is created), and signatures expire.
	creates := 0
	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost:
			creates++
			writeUploadTestResponse(t, w, "file.bin", server.URL+fmt.Sprintf("/signed/%d/file.bin", creates))
		case r.URL.Path == "/signed/1/file.bin":
			http.Error(w, "credentials not yet active", http.StatusUnauthorized)
		case r.URL.Path == "/signed/2/file.bin":
			// fresh URL accepted
		default:
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
			http.Error(w, "unexpected request", http.StatusBadRequest)
		}
	}))
	defer server.Close()

	c := newUploadTestClient(t, server.URL)
	err := c.Upload(context.Background(), "/scope", "file.bin", nil, writeUploadTestFile(t, "data"), UploadOptions{})
	if err != nil {
		t.Fatalf("Upload returned error: %v", err)
	}
	if creates != 2 {
		t.Fatalf("upload URL requested %d times, want 2 (fresh URL per attempt)", creates)
	}
}

func TestUploadSurfacesCompleteFailure(t *testing.T) {
	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method + " " + r.URL.Path {
		case "POST /scope/blobs":
			writeUploadTestResponse(t, w, "file.bin", server.URL+"/signed/file.bin")
		case "PUT /signed/file.bin":
			// storage accepts the bytes
		case "POST /scope/blobs/complete":
			http.Error(w, "boom", http.StatusInternalServerError)
		default:
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
			http.Error(w, "unexpected request", http.StatusBadRequest)
		}
	}))
	defer server.Close()

	c := newUploadTestClient(t, server.URL)
	err := c.Upload(context.Background(), "/scope", "file.bin", nil, writeUploadTestFile(t, "data"),
		UploadOptions{NotifyCompletion: true})
	if err == nil || !strings.Contains(err.Error(), "blobs/complete") {
		t.Fatalf("Upload error = %v, want the complete failure to surface", err)
	}
}
