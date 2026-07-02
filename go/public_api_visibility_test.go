package lit_test

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestGoSDKPublicSurfaceIsMinimal(t *testing.T) {
	entries, err := os.ReadDir(".")
	require.NoError(t, err,
		err)

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		name := entry.Name()
		if strings.HasPrefix(name, ".") || name == "internal" || strings.HasPrefix(name, "_") {
			continue
		}
		assert.Fail(t, fmt.Sprintf("unexpected public Go SDK package %q", name))
	}
}

func TestCoreResourcesDoNotExposeRemoteStateFields(t *testing.T) {
	resourceTypes := map[string]bool{
		"Job":          true,
		"MMT":          true,
		"Organization": true,
		"Studio":       true,
		"Teamspace":    true,
		"User":         true,
	}

	for _, file := range packageFiles(t, ".") {
		parsed, err := parser.ParseFile(token.NewFileSet(), file, nil, 0)
		require.NoError(t, err,
			err)

		for _, decl := range parsed.Decls {
			gen, ok := decl.(*ast.GenDecl)
			if !ok || gen.Tok != token.TYPE {
				continue
			}
			for _, spec := range gen.Specs {
				typeSpec := spec.(*ast.TypeSpec)
				if !resourceTypes[typeSpec.Name.Name] {
					continue
				}
				strct, ok := typeSpec.Type.(*ast.StructType)
				if !ok {
					continue
				}
				for _, field := range strct.Fields.List {
					for _, name := range field.Names {
						assert.Falsef(t, ast.IsExported(name.Name),
							"%s exposes remote state field %s", typeSpec.Name.Name, name.Name)

					}
				}
			}
		}
	}
}

func TestPackageDoesNotExposeNonMinimalTypes(t *testing.T) {
	disallowed := map[string]bool{
		"Agent":              true,
		"AgentOptions":       true,
		"Assistant":          true,
		"CloudAccount":       true,
		"Endpoint":           true,
		"MachineOptions":     true,
		"Model":              true,
		"ModelVersion":       true,
		"Port":               true,
		"UploadModelOptions": true,
		"UploadedModelInfo":  true,
		"VM":                 true,
	}

	for _, file := range packageFiles(t, ".") {
		parsed, err := parser.ParseFile(token.NewFileSet(), file, nil, 0)
		require.NoError(t, err,
			err)

		for _, decl := range parsed.Decls {
			gen, ok := decl.(*ast.GenDecl)
			if !ok || gen.Tok != token.TYPE {
				continue
			}
			for _, spec := range gen.Specs {
				name := spec.(*ast.TypeSpec).Name.Name
				assert.Falsef(t, disallowed[name],
					"package exposes non-minimal type %s", name)

			}
		}
	}
}

func TestTeamspaceOptionsUseCloudField(t *testing.T) {
	for _, file := range packageFiles(t, ".") {
		parsed, err := parser.ParseFile(token.NewFileSet(), file, nil, 0)
		require.NoError(t, err,
			err)

		for _, decl := range parsed.Decls {
			gen, ok := decl.(*ast.GenDecl)
			if !ok || gen.Tok != token.TYPE {
				continue
			}
			for _, spec := range gen.Specs {
				typeSpec := spec.(*ast.TypeSpec)
				if typeSpec.Name.Name != "ConnectionOptions" && typeSpec.Name.Name != "FolderOptions" {
					continue
				}
				strct, ok := typeSpec.Type.(*ast.StructType)
				if !ok {
					continue
				}
				for _, field := range strct.Fields.List {
					for _, name := range field.Names {
						assert.Falsef(t, name.Name == "CloudAccount",
							"%s exposes CloudAccount field; use Cloud", typeSpec.Name.Name)

					}
				}
			}
		}
	}
}

func TestResourceOptionsDoNotExposeReferenceIDsOrOwnerNames(t *testing.T) {
	disallowed := map[string]map[string]bool{
		"StudioOptions": {
			"TeamspaceID": true,
			"User":        true,
			"Org":         true,
		},
		"DuplicateStudioOptions": {
			"TeamspaceID": true,
		},
		"JobOptions": {
			"TeamspaceID": true,
			"User":        true,
			"Org":         true,
			"StudioID":    true,
			"MMTID":       true,
		},
		"MMTOptions": {
			"TeamspaceID": true,
			"User":        true,
			"Org":         true,
			"StudioID":    true,
		},
		"TeamspaceOptions": {
			"User": true,
			"Org":  true,
		},
	}

	for _, file := range packageFiles(t, ".") {
		parsed, err := parser.ParseFile(token.NewFileSet(), file, nil, 0)
		require.NoError(t, err,
			err)

		for _, decl := range parsed.Decls {
			gen, ok := decl.(*ast.GenDecl)
			if !ok || gen.Tok != token.TYPE {
				continue
			}
			for _, spec := range gen.Specs {
				typeSpec := spec.(*ast.TypeSpec)
				fields, ok := disallowed[typeSpec.Name.Name]
				if !ok {
					continue
				}
				strct, ok := typeSpec.Type.(*ast.StructType)
				if !ok {
					continue
				}
				for _, field := range strct.Fields.List {
					for _, name := range field.Names {
						assert.Falsef(t, fields[name.Name],
							"%s exposes %s; pass resource objects instead", typeSpec.Name.Name, name.Name)

					}
				}
			}
		}
	}
}

func TestPackageDoesNotExposeNew(t *testing.T) {
	for _, file := range packageFiles(t, ".") {
		parsed, err := parser.ParseFile(token.NewFileSet(), file, nil, 0)
		require.NoError(t, err,
			err)

		for _, decl := range parsed.Decls {
			fn, ok := decl.(*ast.FuncDecl)
			if !ok || fn.Recv != nil {
				continue
			}
			assert.False(t, fn.Name.Name == "New",
				"package exposes New; use Get for existing remote resources")

		}
	}
}

func TestExportedSymbolsHaveDocComments(t *testing.T) {
	for _, file := range packageFiles(t, ".") {
		parsed, err := parser.ParseFile(token.NewFileSet(), file, nil, parser.ParseComments)
		require.NoError(t, err,
			err)

		for _, decl := range parsed.Decls {
			switch node := decl.(type) {
			case *ast.GenDecl:
				for _, spec := range node.Specs {
					typeSpec, ok := spec.(*ast.TypeSpec)
					if !ok || !ast.IsExported(typeSpec.Name.Name) {
						continue
					}
					assert.Falsef(t, node.Doc == nil,
						"%s is missing a doc comment", typeSpec.Name.Name)

				}
			case *ast.FuncDecl:
				if !ast.IsExported(node.Name.Name) {
					continue
				}
				if node.Doc == nil {
					assert.Fail(t, fmt.Sprintf("%s is missing a doc comment", node.Name.Name))
				}
			}
		}
	}
}

func packageFiles(t *testing.T, pkg string) []string {
	t.Helper()

	entries, err := os.ReadDir(pkg)
	require.NoError(t, err,
		err)

	files := make([]string, 0, len(entries))
	for _, entry := range entries {
		name := entry.Name()
		if entry.IsDir() || !strings.HasSuffix(name, ".go") || strings.HasSuffix(name, "_test.go") {
			continue
		}
		files = append(files, filepath.Join(pkg, name))
	}
	return files
}
