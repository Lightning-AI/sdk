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


def test_cli_has_no_implicit_interaction() -> None:
    violations = []
    for path in CLI_ROOT.rglob("*.py"):
        text = path.read_text()
        for token in FORBIDDEN:
            if token in text:
                violations.append(f"{path.relative_to(CLI_ROOT)}: {token}")
    assert violations == []
