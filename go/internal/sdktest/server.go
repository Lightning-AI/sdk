package sdktest

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func NewAPIServer(t testing.TB, handler http.HandlerFunc) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Cleanup(server.Close)
	return server
}
