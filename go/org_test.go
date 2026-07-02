package lit_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	lit "github.com/gridai/lightning-sdk/go"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestOrgGetWithIDUsesSimpleStruct(t *testing.T) {
	o, err := lit.GetOrganization("acme", lit.OrganizationOptions{ID: "org-1"})
	require.NoErrorf(t, err,
		"GetOrganization returned error")
	assert.Falsef(t, o.ID() != "org-1" || o.Name() != "acme",
		"unexpected org: %s %s", o.ID(), o.Name())

}

func TestOrgStringAndEqual(t *testing.T) {
	o, err := lit.GetOrganization("acme", lit.OrganizationOptions{ID: "org-1"})
	require.NoErrorf(t, err,
		"GetOrganization returned error")

	if got, want := o.String(), "Organization(name=acme)"; got != want {
		assert.Fail(t, fmt.Sprintf("org string = %q, want %q", got, want))
	}
	matching, err := lit.GetOrganization("acme", lit.OrganizationOptions{ID: "org-1"})
	require.NoErrorf(t, err,
		"GetOrganization returned error")
	assert.True(t, o.Equal(matching),
		"matching orgs should be equal")

	other, err := lit.GetOrganization("acme", lit.OrganizationOptions{ID: "org-2"})
	require.NoErrorf(t, err,
		"GetOrganization returned error")
	assert.False(t, o.Equal(other),
		"orgs with different IDs should not be equal")

}

func TestOrgGetResolvesEnvOrg(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		assert.Falsef(t, r.Method != http.MethodGet || r.URL.Path != "/v1/orgs",
			"unexpected request: %s %s", r.Method, r.URL.RequestURI())

		_ = json.NewEncoder(w).Encode(map[string]any{
			"organizations": []map[string]any{{
				"id":               "org-1",
				"name":             "acme",
				"preferredCluster": "aws-us-east",
			}},
		})
	}))
	defer server.Close()
	t.Setenv("LIGHTNING_CLOUD_URL", server.URL)
	t.Setenv("LIGHTNING_ORG", "acme")

	o, err := lit.GetOrganization("")
	require.NoErrorf(t, err,
		"GetOrganization returned error")
	assert.Falsef(t, o.ID() != "org-1" || o.Name() != "acme" || o.DefaultCloudAccount() != "aws-us-east",
		"unexpected org: %+v", o)

}
