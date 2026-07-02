package lit_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	lit "github.com/lightning-ai/sdk/go"
)

func TestUserGetWithIDUsesSimpleStruct(t *testing.T) {
	u, err := lit.GetUser("alice", lit.UserOptions{ID: "user-1"})
	require.NoErrorf(t, err,
		"GetUser returned error")
	assert.Falsef(t, u.ID() != "user-1" || u.Name() != "alice",
		"unexpected user: %s %s", u.ID(), u.Name())

}

func TestUserStringAndEqual(t *testing.T) {
	u, err := lit.GetUser("alice", lit.UserOptions{ID: "user-1"})
	require.NoErrorf(t, err,
		"GetUser returned error")

	if got, want := u.String(), "User(name=alice)"; got != want {
		assert.Fail(t, fmt.Sprintf("user string = %q, want %q", got, want))
	}
	matching, err := lit.GetUser("alice", lit.UserOptions{ID: "user-1"})
	require.NoErrorf(t, err,
		"GetUser returned error")
	assert.True(t, u.Equal(matching),
		"matching users should be equal")

	other, err := lit.GetUser("alice", lit.UserOptions{ID: "user-2"})
	require.NoErrorf(t, err,
		"GetUser returned error")
	assert.False(t, u.Equal(other),
		"users with different IDs should not be equal")

}

func TestUserGetResolvesEnvUsername(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/users/search",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		if got := r.URL.Query().Get("query"); got != "alice" {
			assert.Fail(t, fmt.Sprintf("user search query = %q, want alice", got))
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"users": []map[string]any{{
				"id":       "user-1",
				"username": "alice",
			}},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Setenv("LIGHTNING_USERNAME", "alice")

	u, err := lit.GetUser("")
	require.NoErrorf(t, err,
		"GetUser returned error")
	assert.Falsef(t, u.ID() != "user-1" || u.Name() != "alice",
		"unexpected user: %+v", u)

}
