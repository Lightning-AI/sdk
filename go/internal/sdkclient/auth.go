package sdkclient

import (
	"cmp"
	"context"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const (
	tokenFileEnv = "LIGHTNING_AUTH_TOKEN_FILE"
	authTokenEnv = "LIGHTNING_AUTH_TOKEN"
	apiKeyEnv    = "LIGHTNING_API_KEY"
)

// refreshMargin is how long before expiry an exchanged token is replaced, so
// no request leaves with a token that expires on the way.
const refreshMargin = 5 * time.Minute

const exchangeTimeout = 30 * time.Second

type credentialKind int

const (
	tokenFileCredential credentialKind = iota
	envTokenCredential
	serviceAccountCredential
	savedLoginCredential
)

type credential struct {
	kind  credentialKind
	token string
}

func (c credential) header() string {
	return "Bearer " + c.token
}

// credentialSource works out the credential each request sends, when it is
// sent, so a rotated token file or a re-exchanged token reaches a running
// process.
type credentialSource struct {
	// origin is the base URL the service-account key is exchanged against.
	origin string
	// scheme and host are where requests may carry the credential.
	scheme   string
	host     string
	accounts *serviceAccountCache
}

func newCredentialSource(base *url.URL) *credentialSource {
	return &credentialSource{
		origin:   strings.TrimRight(base.String(), "/"),
		scheme:   strings.ToLower(base.Scheme),
		host:     canonicalHost(base),
		accounts: serviceAccounts,
	}
}

// resolve returns the first credential found, in order of precedence: the
// token file, LIGHTNING_AUTH_TOKEN, the service-account key in
// LIGHTNING_API_KEY, then the saved login. ok is false when there is none.
func (s *credentialSource) resolve(ctx context.Context) (cred credential, ok bool, err error) {
	token, err := tokenFromFile()
	if err != nil {
		return credential{}, false, err
	}
	if token != "" {
		return credential{kind: tokenFileCredential, token: token}, true, nil
	}
	if token := strings.TrimSpace(os.Getenv(authTokenEnv)); token != "" {
		return credential{kind: envTokenCredential, token: token}, true, nil
	}
	if key := strings.TrimSpace(os.Getenv(apiKeyEnv)); key != "" {
		token, err := s.accounts.token(ctx, s.origin, key, "")
		if err != nil {
			return credential{}, false, err
		}
		return credential{kind: serviceAccountCredential, token: token}, true, nil
	}
	if token := savedLoginToken(); token != "" {
		return credential{kind: savedLoginCredential, token: token}, true, nil
	}
	return credential{}, false, nil
}

// authorization returns the Authorization value req should carry, or "" to
// send req as it is: with no credential found, with the caller's own
// Authorization, or to another origin, such as a redirect's target.
func (s *credentialSource) authorization(req *http.Request) (string, error) {
	if s == nil || req.Header.Get("Authorization") != "" || !s.sameOrigin(req.URL) {
		return "", nil
	}
	cred, ok, err := s.resolve(req.Context())
	if err != nil || !ok {
		return "", err
	}
	return cred.header(), nil
}

// refresh reports whether a request refused with 401 after sending sent
// should be sent again: true when a different credential is now available, or
// when the service-account key was exchanged for a new token.
func (s *credentialSource) refresh(ctx context.Context, sent string) (bool, error) {
	current, ok, err := s.resolve(ctx)
	if err != nil || !ok {
		return false, err
	}
	if current.header() != sent {
		return true, nil
	}
	if current.kind != serviceAccountCredential {
		return false, nil
	}
	key := strings.TrimSpace(os.Getenv(apiKeyEnv))
	fresh, err := s.accounts.token(ctx, s.origin, key, current.token)
	if err != nil {
		return false, err
	}
	return fresh != current.token, nil
}

func (s *credentialSource) sameOrigin(u *url.URL) bool {
	return strings.ToLower(u.Scheme) == s.scheme && canonicalHost(u) == s.host
}

func canonicalHost(u *url.URL) string {
	port := u.Port()
	if port == "" {
		switch strings.ToLower(u.Scheme) {
		case "https":
			port = "443"
		case "http":
			port = "80"
		}
	}
	return net.JoinHostPort(strings.ToLower(u.Hostname()), port)
}

// tokenFromFile reads the file LIGHTNING_AUTH_TOKEN_FILE names. A missing or
// blank file holds no credential; one that exists but can't be read is an
// error, so a broken mount isn't silently replaced by another credential.
func tokenFromFile() (string, error) {
	path := os.Getenv(tokenFileEnv)
	if path == "" {
		return "", nil
	}
	raw, err := os.ReadFile(path)
	if errors.Is(err, fs.ErrNotExist) {
		return "", nil
	}
	if err != nil {
		reason := err
		var pathErr *fs.PathError
		if errors.As(err, &pathErr) {
			reason = pathErr.Err
		}
		return "", fmt.Errorf("%s names %s, which can't be read (%v); fix the file or unset %s", tokenFileEnv, path, reason, tokenFileEnv)
	}
	return strings.TrimSpace(string(raw)), nil
}

// savedLoginToken is the auth_token `lightning login` saved in
// credentials.json. A missing file, or one that doesn't parse, holds no
// credential. Its api_key is never sent.
func savedLoginToken() string {
	path, ok := credentialsPath()
	if !ok {
		return ""
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	var saved struct {
		AuthToken string `json:"auth_token"`
	}
	if err := json.Unmarshal(raw, &saved); err != nil {
		return ""
	}
	return strings.TrimSpace(saved.AuthToken)
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

// serviceAccounts holds the token exchanged for LIGHTNING_API_KEY. Every
// client shares it, since each SDK call builds its own client.
var serviceAccounts = newServiceAccountCache(http.DefaultTransport, time.Now)

type serviceAccountCache struct {
	// lock serializes exchanges. It is a channel so a request waiting for
	// another's exchange can give up when its context ends.
	lock    chan struct{}
	client  *http.Client
	now     func() time.Time
	current *exchangedToken
}

type exchangedToken struct {
	// identity is a digest of the origin and key, so a changed key or URL
	// exchanges again.
	identity    [sha256.Size]byte
	accessToken string
	expiresAt   time.Time
}

func newServiceAccountCache(transport http.RoundTripper, now func() time.Time) *serviceAccountCache {
	return &serviceAccountCache{
		lock: make(chan struct{}, 1),
		client: &http.Client{
			Transport: transport,
			Timeout:   exchangeTimeout,
			// The key is sent to the token endpoint only, never to wherever a
			// redirect points.
			CheckRedirect: func(*http.Request, []*http.Request) error {
				return http.ErrUseLastResponse
			},
		},
		now: now,
	}
}

// token returns an access token for key, exchanging it at origin when no
// cached token has more than refreshMargin left. rejected is a token the
// server refused, which forces a new exchange unless another request has
// already replaced it.
func (c *serviceAccountCache) token(ctx context.Context, origin, key, rejected string) (string, error) {
	identity := sha256.Sum256([]byte(origin + "\x00" + key))
	select {
	case c.lock <- struct{}{}:
	case <-ctx.Done():
		return "", ctx.Err()
	}
	defer func() { <-c.lock }()

	var held *exchangedToken
	if c.current != nil && c.current.identity == identity {
		held = c.current
	}
	if held != nil && c.usable(held, rejected) {
		return held.accessToken, nil
	}
	accessToken, expiresIn, err := c.exchange(ctx, origin, key)
	if err != nil {
		// An outage says nothing about the key, so a token with time left
		// keeps working.
		var unavailable *exchangeUnavailableError
		if errors.As(err, &unavailable) && held != nil && rejected == "" && c.now().Before(held.expiresAt) {
			return held.accessToken, nil
		}
		return "", err
	}
	c.current = &exchangedToken{identity: identity, accessToken: accessToken, expiresAt: c.now().Add(expiresIn)}
	return accessToken, nil
}

func (c *serviceAccountCache) usable(held *exchangedToken, rejected string) bool {
	if rejected != "" {
		return held.accessToken != rejected
	}
	return held.expiresAt.Sub(c.now()) >= refreshMargin
}

// exchangeUnavailableError is an exchange that got an answer about the server,
// not about the key.
type exchangeUnavailableError struct {
	message string
	err     error
}

func (e *exchangeUnavailableError) Error() string { return e.message }

func (e *exchangeUnavailableError) Unwrap() error { return e.err }

func (c *serviceAccountCache) exchange(ctx context.Context, origin, key string) (string, time.Duration, error) {
	// No client_id: the key alone names its account.
	form := url.Values{"grant_type": {"client_credentials"}, "client_secret": {key}}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, origin+"/oidc/token", strings.NewReader(form.Encode()))
	if err != nil {
		return "", 0, err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := c.client.Do(req)
	if err != nil {
		return "", 0, &exchangeUnavailableError{
			message: fmt.Sprintf("couldn't reach %s to exchange %s; check your connection and try again", origin, apiKeyEnv),
			err:     err,
		}
	}
	defer func() { _ = resp.Body.Close() }()

	var body struct {
		AccessToken      any `json:"access_token"`
		ExpiresIn        any `json:"expires_in"`
		Error            any `json:"error"`
		ErrorDescription any `json:"error_description"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&body); err != nil {
		body.AccessToken, body.ExpiresIn, body.Error, body.ErrorDescription = nil, nil, nil, nil
	}
	errorCode := jsonText(body.Error)
	switch status := resp.StatusCode; {
	case status == http.StatusOK:
		accessToken, _ := body.AccessToken.(string)
		seconds, _ := body.ExpiresIn.(float64)
		if accessToken == "" || seconds <= 0 {
			return "", 0, fmt.Errorf("the %s exchange returned no usable token", apiKeyEnv)
		}
		return accessToken, time.Duration(seconds * float64(time.Second)), nil
	case status == http.StatusUnauthorized && errorCode == "invalid_client":
		reason := cmp.Or(jsonText(body.ErrorDescription), "invalid service account key")
		return "", 0, fmt.Errorf("%s was refused: %s; use a current key, or unset %s to use your login", apiKeyEnv, reason, apiKeyEnv)
	case status == http.StatusBadRequest && errorCode == "unsupported_grant_type":
		return "", 0, fmt.Errorf("%s doesn't accept service-account keys; unset %s to use your login", origin, apiKeyEnv)
	case status >= 500 || status == http.StatusTooManyRequests:
		return "", 0, &exchangeUnavailableError{
			message: fmt.Sprintf("the %s exchange returned %d; try again shortly", apiKeyEnv, status),
		}
	default:
		return "", 0, errors.New(strings.TrimSpace(fmt.Sprintf("the %s exchange returned %d %s", apiKeyEnv, status, errorCode)))
	}
}

func jsonText(value any) string {
	switch v := value.(type) {
	case nil:
		return ""
	case string:
		return v
	default:
		return fmt.Sprint(v)
	}
}
