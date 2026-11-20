package sdkclient

import (
	"fmt"
	"regexp"
	"runtime/debug"
	"strconv"
	"sync"
)

const modulePath = "github.com/lightning-ai/sdk/go"

// userAgent names this SDK and its release, which the platform checks against
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

var (
	releaseVersion = regexp.MustCompile(`^v0\.([0-9]{4})([0-9]{2})([0-9]{2})\.(0|[1-9][0-9]*)$`)
	pseudoVersion  = regexp.MustCompile(`^v[0-9]+\.[0-9]+\.[0-9]+-(?:.+\.)?([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{6})-([0-9a-f]{12})(?:\+.*)?$`)
)

// sdkVersion turns a module version back into the release the platform
// compares. Go reads only semantic versions, so release vYYYY.MM.DD is tagged
// v0.YYYYMMDD.0 and its vYYYY.MM.DD.postN v0.YYYYMMDD.(N+1)
// (.github/scripts/go_release_tag.py). A commit fetched by pseudo-version,
// such as v0.20261113.1-0.20261114150405-abcdef123456, becomes the dev build
// 2026.11.14.dev150405+abcdef123456, which sorts before that day's release.
// Anything else is "dev", which the platform treats as older than every
// release.
func sdkVersion(version string) string {
	if m := releaseVersion.FindStringSubmatch(version); m != nil {
		release := m[1] + "." + m[2] + "." + m[3]
		patch, _ := strconv.Atoi(m[4])
		if patch == 0 {
			return release
		}
		return fmt.Sprintf("%s.post%d", release, patch-1)
	}
	if m := pseudoVersion.FindStringSubmatch(version); m != nil {
		return fmt.Sprintf("%s.%s.%s.dev%s+%s", m[1], m[2], m[3], m[4], m[5])
	}
	return "dev"
}
