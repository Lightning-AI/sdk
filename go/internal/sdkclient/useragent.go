package sdkclient

import (
	"fmt"
	"regexp"
	"runtime/debug"
	"strings"
	"sync"
)

const modulePath = "github.com/lightning-ai/sdk/go"

// userAgent names this SDK and its version, which the platform checks against
// the minimum Go SDK it supports.
var userAgent = sync.OnceValue(func() string {
	return "lightning-sdk-go/" + sdkVersion(moduleVersion())
})

func moduleVersion() string {
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return ""
	}
	if info.Main.Path == modulePath {
		return info.Main.Version
	}
	for _, dep := range info.Deps {
		if dep.Path != modulePath {
			continue
		}
		if dep.Replace != nil && dep.Replace.Version != "" {
			return dep.Replace.Version
		}
		return dep.Version
	}
	return ""
}

var pseudoVersion = regexp.MustCompile(`^v[0-9]+\.[0-9]+\.[0-9]+-(?:.+\.)?([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{6})-([0-9a-f]{12})(?:\+.*)?$`)

// sdkVersion turns a module version into the calendar version the platform
// compares. The repository's release tags aren't Go module tags, so the module
// is fetched by commit as a pseudo-version such as
// v0.0.0-20261113150405-abcdef123456. That becomes the dev build
// 2026.11.13.dev150405+abcdef123456, which sorts after every release before
// the commit's day and before any release from that day on.
func sdkVersion(version string) string {
	if version == "" || version == "(devel)" {
		return "dev"
	}
	if m := pseudoVersion.FindStringSubmatch(version); m != nil {
		return fmt.Sprintf("%s.%s.%s.dev%s+%s", m[1], m[2], m[3], m[4], m[5])
	}
	return strings.TrimPrefix(version, "v")
}
