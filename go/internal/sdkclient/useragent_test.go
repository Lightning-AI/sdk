package sdkclient

import (
	"strings"
	"testing"
)

func TestUserAgentNamesTheGoSDK(t *testing.T) {
	if got := userAgent(); !strings.HasPrefix(got, "lightning-sdk-go/") {
		t.Fatalf("userAgent() = %q, want lightning-sdk-go/<version>", got)
	}
}

func TestSDKVersion(t *testing.T) {
	for version, want := range map[string]string{
		"v0.20261120.0": "2026.11.20",
		"v0.20261120.1": "2026.11.20.post0",
		"v0.20261120.3": "2026.11.20.post2",
		"v0.20261120.1-0.20261121093000-abcdef123456":       "2026.11.21.dev093000+abcdef123456",
		"v0.20261120.1-0.20261121093000-abcdef123456+dirty": "2026.11.21.dev093000+abcdef123456",
		"v0.0.0-20261113150405-abcdef123456":                "2026.11.13.dev150405+abcdef123456",
		"":                                                  "dev",
		"(devel)":                                           "dev",
		"v1.2.3":                                            "dev",
	} {
		if got := sdkVersion(version); got != want {
			t.Errorf("sdkVersion(%q) = %q, want %q", version, got, want)
		}
	}
}
