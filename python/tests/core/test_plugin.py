import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[2] / "lightning_sdk"


def test_plugin_module_is_not_publicly_available():
    assert not (PACKAGE_ROOT / "plugin.py").exists()


def test_lightning_sdk_does_not_export_plugin_classes():
    removed_exports = {
        "JobsPlugin",
        "MultiMachineTrainingPlugin",
        "Plugin",
        "SlurmJobsPlugin",
    }
    module = ast.parse((PACKAGE_ROOT / "__init__.py").read_text())

    imported_names = {
        alias.asname or alias.name for node in module.body if isinstance(node, ast.ImportFrom) for alias in node.names
    }
    exported_names = {
        element.value
        for node in module.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "__all__"
        if isinstance(node.value, ast.List)
        for element in node.value.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    }

    assert removed_exports.isdisjoint(imported_names)
    assert removed_exports.isdisjoint(exported_names)


def test_studio_does_not_expose_plugin_helpers():
    removed_helpers = {
        "available_plugins",
        "install_plugin",
        "installed_plugins",
        "run_plugin",
        "uninstall_plugin",
        "_add_plugin",
        "_execute_plugin",
        "_list_installed_plugins",
    }
    module = ast.parse((PACKAGE_ROOT / "studio.py").read_text())
    studio_class = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Studio")
    studio_members = {
        node.name for node in studio_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert removed_helpers.isdisjoint(studio_members)


def test_handwritten_sdk_does_not_import_plugin_module():
    handwritten_sources = (
        path for path in PACKAGE_ROOT.rglob("*.py") if "lightning_cloud/openapi" not in path.as_posix()
    )

    for path in handwritten_sources:
        assert "lightning_sdk.plugin" not in path.read_text(), path


def test_studio_init_tests_do_not_mock_plugin_list_endpoints():
    tests_root = PACKAGE_ROOT.parent / "tests"
    init_path_sources = [tests_root / "conftest.py", *list((tests_root / "core" / "studio").rglob("*.py"))]
    removed_init_markers = {
        "cloud_space_service_list_available_plugins",
        "cloud_space_service_list_installed_plugins",
        "mock_list_available_plugins",
        "mock_list_installed_plugins",
        "V1PluginsListResponse",
    }

    for path in init_path_sources:
        contents = path.read_text()
        for marker in removed_init_markers:
            assert marker not in contents, path
