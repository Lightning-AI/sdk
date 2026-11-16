package sdktest

import (
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

func NewAPIServer(t testing.TB, handler http.HandlerFunc) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(handler)
	UseAPI(t, server.URL)
	t.Cleanup(server.Close)
	return server
}

// UseAPI points the SDK at url for the rest of the test, with no credential
// from the environment or a saved login.
func UseAPI(t testing.TB, url string) {
	t.Helper()
	t.Setenv("LIGHTNING_CLOUD_URL", url)
	ClearCredentials(t)
}

// ClearCredentials hides every credential the developer's shell or saved login
// would otherwise supply, so a test sees only those it sets itself.
func ClearCredentials(t testing.TB) {
	t.Helper()
	for _, name := range []string{
		"LIGHTNING_AUTH_TOKEN_FILE",
		"LIGHTNING_AUTH_TOKEN",
		"LIGHTNING_API_KEY",
		"LIGHTNING_USER_ID",
	} {
		t.Setenv(name, "")
	}
	t.Setenv("LIGHTNING_CREDENTIAL_PATH", filepath.Join(t.TempDir(), "credentials.json"))
}
