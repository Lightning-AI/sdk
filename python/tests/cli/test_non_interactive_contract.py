from pathlib import Path

CLI_ROOT = Path(__file__).parents[2] / "lightning_sdk" / "cli"
FORBIDDEN = (
    "TerminalMenu",
    "simple_term_menu",
    "inquirer",
    "click.confirm",
    "Confirm.ask",
    "LIGHTNING_NON_INTERACTIVE",
    "webbrowser.open",
)
ALLOWED = {("utils/delete.py", "click.confirm")}


def test_cli_has_no_implicit_interaction() -> None:
    violations = []
    for path in CLI_ROOT.rglob("*.py"):
        text = path.read_text()
        for token in FORBIDDEN:
            relative_path = path.relative_to(CLI_ROOT).as_posix()
            if token in text and (relative_path, token) not in ALLOWED:
                violations.append(f"{relative_path}: {token}")
    assert violations == []
