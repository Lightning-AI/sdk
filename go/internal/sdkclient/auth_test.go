package sdkclient

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/lightning-ai/sdk/go/internal/sdktest"
)

// fakePlatform serves the API and its /oidc/token exchange, recording what
// each request carried.
type fakePlatform struct {
	*httptest.Server

	mu sync.Mutex
	// apiRequests and exchanges are the API and exchange requests received.
	apiRequests []recordedRequest
	exchanges   []recordedRequest
	// exchangeReply answers the nth exchange, counting from 1; nil issues the
	// token sa-<n> for an hour.
	exchangeReply func(n int) (status int, body string)
	// apiStatus answers an API request by its Authorization; nil answers 200.
	apiStatus func(authorization string) int
}

type recordedRequest struct {
	method string
	header http.Header
	body   string
	form   url.Values
}

func newFakePlatform(t *testing.T) *fakePlatform {
	t.Helper()
	p := &fakePlatform{}
	p.Server = httptest.NewServer(http.HandlerFunc(p.serve))
	t.Cleanup(p.Close)
	return p
}

func (p *fakePlatform) serve(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/oidc/token" {
		_ = r.ParseForm()
		p.mu.Lock()
		p.exchanges = append(p.exchanges, recordedRequest{method: r.Method, header: r.Header.Clone(), form: r.PostForm})
		n := len(p.exchanges)
		reply := p.exchangeReply
		p.mu.Unlock()
		if reply == nil {
			reply = issued
		}
		status, body := reply(n)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = io.WriteString(w, body)
		return
	}
	body, _ := io.ReadAll(r.Body)
	authorization := r.Header.Get("Authorization")
	p.mu.Lock()
	p.apiRequests = append(p.apiRequests, recordedRequest{method: r.Method, header: r.Header.Clone(), body: string(body)})
	apiStatus := p.apiStatus
	p.mu.Unlock()
	status := http.StatusOK
	if apiStatus != nil {
		status = apiStatus(authorization)
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = io.WriteString(w, "{}")
}

func issued(n int) (int, string) {
	return http.StatusOK, fmt.Sprintf(`{"access_token":"sa-%d","token_type":"Bearer","expires_in":3600}`, n)
}

func (p *fakePlatform) received() (apiRequests, exchanges []recordedRequest) {
	p.mu.Lock()
	defer p.mu.Unlock()
	return append([]recordedRequest(nil), p.apiRequests...), append([]recordedRequest(nil), p.exchanges...)
}

func (p *fakePlatform) authorizations() []string {
	apiRequests, _ := p.received()
	var sent []string
	for _, r := range apiRequests {
		sent = append(sent, r.header.Get("Authorization"))
	}
	return sent
}

func (p *fakePlatform) lastAuthorization(t *testing.T) string {
	t.Helper()
	sent := p.authorizations()
	if len(sent) == 0 {
		t.Fatal("no API request was sent")
	}
	return sent[len(sent)-1]
}

func (p *fakePlatform) exchangeCount() int {
	_, exchanges := p.received()
	return len(exchanges)
}

func (p *fakePlatform) bodies() []string {
	apiRequests, _ := p.received()
	var bodies []string
	for _, r := range apiRequests {
		bodies = append(bodies, r.body)
	}
	return bodies
}

type fakeClock struct {
	mu  sync.Mutex
	now time.Time
}

func newFakeClock() *fakeClock {
	return &fakeClock{now: time.Date(2026, 11, 16, 12, 0, 0, 0, time.UTC)}
}

func (c *fakeClock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.now
}

func (c *fakeClock) Advance(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.now = c.now.Add(d)
}

// newTestRawClient returns a client for serverURL that sends each request
// once, exchanging service-account keys through accounts.
func newTestRawClient(t *testing.T, serverURL string, accounts *serviceAccountCache) *RawClient {
	t.Helper()
	parsed, err := url.Parse(serverURL)
	if err != nil {
		t.Fatal(err)
	}
	source := newCredentialSource(parsed)
	source.accounts = accounts
	return &RawClient{
		baseURL:    parsed,
		httpClient: &http.Client{Transport: retryTransport{maxTries: 1, credentials: source}},
	}
}

func newTestAccounts(clock *fakeClock) *serviceAccountCache {
	return newServiceAccountCache(http.DefaultTransport, clock.Now)
}

func get(c *RawClient) error {
	return c.Do(context.Background(), http.MethodGet, "/v1/ping", nil, nil, nil)
}

func mustGet(t *testing.T, c *RawClient) {
	t.Helper()
	if err := get(c); err != nil {
		t.Fatalf("request failed: %v", err)
	}
}

func writeCredentialsFile(t *testing.T, body string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "credentials.json")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("LIGHTNING_CREDENTIAL_PATH", path)
}

func writeTokenFile(t *testing.T, contents string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "token")
	if err := os.WriteFile(path, []byte(contents), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv(tokenFileEnv, path)
	return path
}

func TestCredentialPrecedence(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	writeCredentialsFile(t, `{"auth_token":"saved-token","api_key":"saved-key"}`)
	t.Setenv(apiKeyEnv, "lit_sa_key")
	t.Setenv(authTokenEnv, "env-token")
	writeTokenFile(t, "file-token\n")

	for _, step := range []struct {
		unset string
		want  string
	}{
		{want: "Bearer file-token"},
		{unset: tokenFileEnv, want: "Bearer env-token"},
		{unset: authTokenEnv, want: "Bearer sa-1"},
		{unset: apiKeyEnv, want: "Bearer saved-token"},
	} {
		if step.unset != "" {
			t.Setenv(step.unset, "")
		}
		mustGet(t, c)
		if got := p.lastAuthorization(t); got != step.want {
			t.Fatalf("after unsetting %q: Authorization = %q, want %q", step.unset, got, step.want)
		}
	}
}

func TestTokenFileIsReadForEveryRequest(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	path := writeTokenFile(t, "first")

	mustGet(t, c)
	if err := os.WriteFile(path, []byte("second"), 0o600); err != nil {
		t.Fatal(err)
	}
	mustGet(t, c)

	got := p.authorizations()
	if len(got) != 2 || got[0] != "Bearer first" || got[1] != "Bearer second" {
		t.Fatalf("Authorization headers = %q, want the token before and after rotation", got)
	}
}

func TestUnreadableTokenFileFailsBeforeSending(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	t.Setenv(authTokenEnv, "env-token")
	// A directory exists but can't be read as a file, whoever runs the test.
	dir := t.TempDir()
	t.Setenv(tokenFileEnv, dir)

	err := get(c)
	if err == nil || !strings.Contains(err.Error(), tokenFileEnv) || !strings.Contains(err.Error(), dir) {
		t.Fatalf("error = %v, want one naming %s and %s", err, tokenFileEnv, dir)
	}
	if sent := p.authorizations(); len(sent) != 0 {
		t.Fatalf("sent %d requests, want none", len(sent))
	}
}

func TestMissingOrBlankTokenFileFallsThrough(t *testing.T) {
	for name, setup := range map[string]func(t *testing.T){
		"missing": func(t *testing.T) { t.Setenv(tokenFileEnv, filepath.Join(t.TempDir(), "absent")) },
		"blank":   func(t *testing.T) { writeTokenFile(t, " \n\t") },
	} {
		t.Run(name, func(t *testing.T) {
			sdktest.ClearCredentials(t)
			p := newFakePlatform(t)
			c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
			t.Setenv(authTokenEnv, "env-token")
			setup(t)

			mustGet(t, c)
			if got := p.lastAuthorization(t); got != "Bearer env-token" {
				t.Fatalf("Authorization = %q, want the environment token", got)
			}
		})
	}
}

func TestUserIDNeverSendsBasic(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	t.Setenv("LIGHTNING_USER_ID", "user-1")
	t.Setenv(authTokenEnv, "env-token")

	mustGet(t, c)
	if got := p.lastAuthorization(t); got != "Bearer env-token" {
		t.Fatalf("Authorization = %q, want the bearer token alone", got)
	}
}

func TestSavedAPIKeyIsNotSent(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	t.Setenv("LIGHTNING_USER_ID", "user-1")
	writeCredentialsFile(t, `{"user_id":"user-1","api_key":"saved-key"}`)

	mustGet(t, c)
	if got := p.lastAuthorization(t); got != "" {
		t.Fatalf("Authorization = %q, want none", got)
	}
}

func TestMalformedCredentialsFileHoldsNoCredential(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	writeCredentialsFile(t, `{bad json`)

	mustGet(t, c)
	if got := p.lastAuthorization(t); got != "" {
		t.Fatalf("Authorization = %q, want none", got)
	}
}

func TestServiceAccountKeyIsExchangedAndOnlyTheTokenSent(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	t.Setenv(apiKeyEnv, " lit_sa_key\n")

	mustGet(t, c)
	mustGet(t, c)

	if got := p.authorizations(); len(got) != 2 || got[0] != "Bearer sa-1" || got[1] != "Bearer sa-1" {
		t.Fatalf("Authorization headers = %q, want the exchanged token twice", got)
	}
	apiRequests, exchanges := p.received()
	if len(exchanges) != 1 {
		t.Fatalf("exchanged %d times, want 1 with the token cached", len(exchanges))
	}
	exchange := exchanges[0]
	if exchange.method != http.MethodPost {
		t.Errorf("exchange method = %s, want POST", exchange.method)
	}
	if got := exchange.header.Get("Content-Type"); got != "application/x-www-form-urlencoded" {
		t.Errorf("exchange Content-Type = %q", got)
	}
	if got := exchange.header.Get("Authorization"); got != "" {
		t.Errorf("exchange Authorization = %q, want none", got)
	}
	if got := exchange.header.Get("User-Agent"); got != userAgent() {
		t.Errorf("exchange User-Agent = %q, want %q", got, userAgent())
	}
	if got := apiRequests[0].header.Get("User-Agent"); got != userAgent() {
		t.Errorf("API request User-Agent = %q, want %q", got, userAgent())
	}
	want := url.Values{"grant_type": {"client_credentials"}, "client_secret": {"lit_sa_key"}}
	if exchange.form.Encode() != want.Encode() {
		t.Errorf("exchange form = %v, want %v", exchange.form, want)
	}
	for _, r := range apiRequests {
		for name, values := range r.header {
			for _, value := range values {
				if strings.Contains(value, "lit_sa_key") {
					t.Errorf("API request header %s carried the key", name)
				}
			}
		}
	}

	t.Setenv(apiKeyEnv, "lit_sa_other")
	mustGet(t, c)
	if got := p.lastAuthorization(t); got != "Bearer sa-2" {
		t.Fatalf("after changing the key: Authorization = %q, want a new exchange", got)
	}
}

func TestServiceAccountTokenIsReplacedNearExpiry(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	clock := newFakeClock()
	c := newTestRawClient(t, p.URL, newTestAccounts(clock))
	t.Setenv(apiKeyEnv, "lit_sa_key")

	mustGet(t, c)
	clock.Advance(time.Hour - refreshMargin)
	mustGet(t, c)
	if got := p.lastAuthorization(t); got != "Bearer sa-1" {
		t.Fatalf("with the margin left: Authorization = %q, want the cached token", got)
	}
	clock.Advance(time.Second)
	mustGet(t, c)
	if got := p.lastAuthorization(t); got != "Bearer sa-2" {
		t.Fatalf("inside the margin: Authorization = %q, want a new exchange", got)
	}
}

func TestServiceAccountTokenIsReplacedAfterUnauthorized(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	p.apiStatus = func(authorization string) int {
		if authorization == "Bearer sa-1" {
			return http.StatusUnauthorized
		}
		return http.StatusOK
	}
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	t.Setenv(apiKeyEnv, "lit_sa_key")

	err := c.Do(context.Background(), http.MethodPost, "/v1/things", nil, map[string]string{"name": "x"}, nil)
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	if got := p.authorizations(); len(got) != 2 || got[0] != "Bearer sa-1" || got[1] != "Bearer sa-2" {
		t.Fatalf("Authorization headers = %q, want the refused token then a new one", got)
	}
	if bodies := p.bodies(); bodies[0] == "" || bodies[1] != bodies[0] {
		t.Fatalf("bodies = %q, want the same body resent", bodies)
	}
}

func TestServiceAccountKeyRefusedAfterUnauthorizedIsReported(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	p.exchangeReply = func(n int) (int, string) {
		if n == 1 {
			return issued(n)
		}
		return http.StatusUnauthorized, `{"error":"invalid_client","error_description":"service account key revoked"}`
	}
	p.apiStatus = func(string) int { return http.StatusUnauthorized }
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	t.Setenv(apiKeyEnv, "lit_sa_key")

	err := get(c)
	if err == nil || !strings.Contains(err.Error(), "service account key revoked") {
		t.Fatalf("error = %v, want the refused key's reason", err)
	}
	if sent := p.authorizations(); len(sent) != 1 {
		t.Fatalf("sent %d API requests, want 1", len(sent))
	}
}

func TestServiceAccountKeepsUnexpiredTokenWhileExchangeIsDown(t *testing.T) {
	for _, tc := range []struct {
		name   string
		status int
		want   string
	}{
		{name: "server error", status: http.StatusServiceUnavailable, want: "returned 503"},
		{name: "throttled", status: http.StatusTooManyRequests, want: "returned 429"},
		{name: "unreachable", want: "couldn't reach"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			sdktest.ClearCredentials(t)
			p := newFakePlatform(t)
			var down atomic.Bool
			p.exchangeReply = func(n int) (int, string) {
				if down.Load() {
					return tc.status, `{"error":"temporarily_unavailable"}`
				}
				return issued(n)
			}
			transport := http.DefaultTransport
			if tc.status == 0 {
				transport = roundTripFunc(func(req *http.Request) (*http.Response, error) {
					if down.Load() {
						return nil, errors.New("connection refused")
					}
					return http.DefaultTransport.RoundTrip(req)
				})
			}
			clock := newFakeClock()
			c := newTestRawClient(t, p.URL, newServiceAccountCache(transport, clock.Now))
			t.Setenv(apiKeyEnv, "lit_sa_key")

			mustGet(t, c)
			down.Store(true)
			clock.Advance(58 * time.Minute)
			mustGet(t, c)
			if got := p.lastAuthorization(t); got != "Bearer sa-1" {
				t.Fatalf("before expiry: Authorization = %q, want the cached token", got)
			}

			clock.Advance(2 * time.Minute)
			err := get(c)
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("after expiry: error = %v, want %q", err, tc.want)
			}
			if sent := p.authorizations(); len(sent) != 2 {
				t.Fatalf("sent %d API requests, want 2", len(sent))
			}
		})
	}
}

func TestServiceAccountExchangeErrors(t *testing.T) {
	for _, tc := range []struct {
		name   string
		status int
		body   string
		want   string
	}{
		{
			name:   "refused key",
			status: http.StatusUnauthorized,
			body:   `{"error":"invalid_client","error_description":"service account key revoked"}`,
			want:   "LIGHTNING_API_KEY was refused: service account key revoked",
		},
		{
			name:   "refused key without a reason",
			status: http.StatusUnauthorized,
			body:   `{"error":"invalid_client"}`,
			want:   "LIGHTNING_API_KEY was refused: invalid service account key",
		},
		{
			name:   "grant not offered",
			status: http.StatusBadRequest,
			body:   `{"error":"unsupported_grant_type"}`,
			want:   "doesn't accept service-account keys",
		},
		{
			name:   "no expiry",
			status: http.StatusOK,
			body:   `{"access_token":"sa-1"}`,
			want:   "returned no usable token",
		},
		{
			name:   "other refusal",
			status: http.StatusForbidden,
			body:   `{"error":"access_denied"}`,
			want:   "returned 403 access_denied",
		},
	} {
		t.Run(tc.name, func(t *testing.T) {
			sdktest.ClearCredentials(t)
			p := newFakePlatform(t)
			p.exchangeReply = func(int) (int, string) { return tc.status, tc.body }
			c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
			t.Setenv(apiKeyEnv, "lit_sa_key")
			writeCredentialsFile(t, `{"auth_token":"saved-token"}`)

			err := get(c)
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("error = %v, want %q", err, tc.want)
			}
			if sent := p.authorizations(); len(sent) != 0 {
				t.Fatalf("sent %d API requests, want none", len(sent))
			}
		})
	}
}

func TestServiceAccountExchangesAreSerialized(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	t.Setenv(apiKeyEnv, "lit_sa_key")

	var wg sync.WaitGroup
	errs := make(chan error, 16)
	for range 16 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			errs <- get(c)
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		if err != nil {
			t.Fatalf("request failed: %v", err)
		}
	}
	if n := p.exchangeCount(); n != 1 {
		t.Fatalf("exchanged %d times, want 1", n)
	}
}

func TestUnauthorizedIsResentOnceWithANewCredential(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	path := writeTokenFile(t, "old")
	p.apiStatus = func(authorization string) int {
		if authorization == "Bearer old" {
			if err := os.WriteFile(path, []byte("new"), 0o600); err != nil {
				t.Error(err)
			}
			return http.StatusUnauthorized
		}
		return http.StatusOK
	}
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))

	err := c.Do(context.Background(), http.MethodPost, "/v1/things", nil, map[string]string{"name": "x"}, nil)
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	if got := p.authorizations(); len(got) != 2 || got[0] != "Bearer old" || got[1] != "Bearer new" {
		t.Fatalf("Authorization headers = %q, want the old token then the new one", got)
	}
	if bodies := p.bodies(); bodies[0] == "" || bodies[1] != bodies[0] {
		t.Fatalf("bodies = %q, want the same body resent", bodies)
	}
}

func TestUnauthorizedWithTheSameCredentialIsNotResent(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	p.apiStatus = func(string) int { return http.StatusUnauthorized }
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))
	t.Setenv(authTokenEnv, "env-token")

	err := get(c)
	if err == nil || !strings.Contains(err.Error(), "401") {
		t.Fatalf("error = %v, want the 401", err)
	}
	if sent := p.authorizations(); len(sent) != 1 {
		t.Fatalf("sent %d requests, want 1", len(sent))
	}
}

func TestUnauthorizedIsResentAtMostOnce(t *testing.T) {
	sdktest.ClearCredentials(t)
	p := newFakePlatform(t)
	path := writeTokenFile(t, "token-0")
	var refusals atomic.Int32
	p.apiStatus = func(string) int {
		n := refusals.Add(1)
		if err := os.WriteFile(path, fmt.Appendf(nil, "token-%d", n), 0o600); err != nil {
			t.Error(err)
		}
		return http.StatusUnauthorized
	}
	c := newTestRawClient(t, p.URL, newTestAccounts(newFakeClock()))

	if err := get(c); err == nil || !strings.Contains(err.Error(), "401") {
		t.Fatalf("error = %v, want the 401", err)
	}
	if sent := p.authorizations(); len(sent) != 2 {
		t.Fatalf("sent %d requests, want 2", len(sent))
	}
}

func TestCallerAuthorizationIsKept(t *testing.T) {
	sdktest.ClearCredentials(t)
	writeTokenFile(t, "file-token")
	var sent []string
	transport := retryTransport{
		maxTries:    1,
		credentials: newCredentialSource(&url.URL{Scheme: "https", Host: "example.test"}),
		base: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			sent = append(sent, req.Header.Get("Authorization"))
			return response(http.StatusUnauthorized, "no"), nil
		}),
	}
	req := request(t, http.MethodGet, nil)
	req.Header.Set("Authorization", "Bearer mine")

	resp, err := transport.RoundTrip(req)
	if err != nil {
		t.Fatalf("RoundTrip returned error: %v", err)
	}
	_ = resp.Body.Close()
	if len(sent) != 1 || sent[0] != "Bearer mine" {
		t.Fatalf("Authorization headers = %q, want the caller's, sent once", sent)
	}
}

func TestUnreplayableBodyIsNotResent(t *testing.T) {
	sdktest.ClearCredentials(t)
	path := writeTokenFile(t, "old")
	attempts := 0
	transport := retryTransport{
		maxTries:    1,
		credentials: newCredentialSource(&url.URL{Scheme: "https", Host: "example.test"}),
		base: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			attempts++
			if err := os.WriteFile(path, []byte("new"), 0o600); err != nil {
				t.Fatal(err)
			}
			return response(http.StatusUnauthorized, "no"), nil
		}),
	}
	req := request(t, http.MethodPost, io.NopCloser(strings.NewReader("streamed")))

	resp, err := transport.RoundTrip(req)
	if err != nil {
		t.Fatalf("RoundTrip returned error: %v", err)
	}
	_ = resp.Body.Close()
	if attempts != 1 {
		t.Fatalf("attempts = %d, want 1", attempts)
	}
}

func TestCredentialIsNotSentToAnotherOrigin(t *testing.T) {
	sdktest.ClearCredentials(t)
	t.Setenv(authTokenEnv, "env-token")
	var mu sync.Mutex
	seen := map[string]string{}
	record := func(server string, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		seen[server] = r.Header.Get("Authorization")
	}
	other := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		record("other", r)
		_, _ = io.WriteString(w, "{}")
	}))
	defer other.Close()
	api := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		record("api", r)
		http.Redirect(w, r, other.URL+"/landing", http.StatusFound)
	}))
	defer api.Close()
	c := newTestRawClient(t, api.URL, newTestAccounts(newFakeClock()))

	mustGet(t, c)
	mu.Lock()
	defer mu.Unlock()
	if got, ok := seen["api"]; !ok || got != "Bearer env-token" {
		t.Fatalf("API Authorization = %q, want the token", got)
	}
	if got, ok := seen["other"]; !ok || got != "" {
		t.Fatalf("redirect target Authorization = %q (reached: %v), want none", got, ok)
	}
}
