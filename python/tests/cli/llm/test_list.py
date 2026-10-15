import json

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.llm.list import LIST_KEYS, list_llms
from tests.cli.help import assert_help_contains, command_text, mock_command_logging, run_cli


def _names(text: str) -> list:
    """Model names from the first column of the rendered table, in display order."""
    return [line.split("│")[1].strip() for line in text.splitlines() if line.startswith("│")]


@mock_command_logging
def test_llm_list_help() -> None:
    assert_help_contains(
        "lightning llm list --help",
        "Usage: lightning llm list",
        "List hosted LLMs available through the Lightning model gateway.",
    )


@mock_command_logging
def test_llms_alias_list_help() -> None:
    assert_help_contains("lightning llms list --help", "Usage: lightning llms list")


@mock_command_logging
def test_llm_list_table_shows_callable_names_and_prices_per_million(published_llm_endpoints) -> None:
    text = command_text("lightning llm list")

    assert "mge_" not in text
    assert _names(text) == [
        "google/gemini-2.5-flash",
        "lightning-ai/gemma-4-31B-it",
        "lightning-ai/glm-5.3",
        "openai/gpt-4-turbo",
        "openai/gpt-5",
    ]
    gpt5 = next(line for line in text.splitlines() if "openai/gpt-5 " in line)
    assert [cell.strip() for cell in gpt5.split("│")[2:6]] == ["400000", "1.25", "10", "ONLINE"]


@mock_command_logging
def test_llm_list_filter_by_provider_keeps_open_weights_models(published_llm_endpoints) -> None:
    text = command_text("lightning llm list --filter provider=lightning-ai")

    assert _names(text) == ["lightning-ai/gemma-4-31B-it", "lightning-ai/glm-5.3"]


@mock_command_logging
def test_llm_list_filters_combine_and_match_displayed_values(published_llm_endpoints) -> None:
    text = command_text("lightning llm list --filter 'context=131072,status=online'")

    assert _names(text) == ["lightning-ai/glm-5.3"]


@mock_command_logging
def test_llm_list_sorts_prices_numerically(published_llm_endpoints) -> None:
    text = command_text("lightning llm list --sort-by prompt-price")

    # Prompt prices 0.14, 0.3, 1.25, 2, 10: a text sort would put 10 before 2.
    assert _names(text) == [
        "lightning-ai/gemma-4-31B-it",
        "google/gemini-2.5-flash",
        "openai/gpt-5",
        "lightning-ai/glm-5.3",
        "openai/gpt-4-turbo",
    ]


@mock_command_logging
def test_llm_list_json_shape(published_llm_endpoints) -> None:
    rows = json.loads(run_cli("lightning llm list --json --filter name=lightning-ai/glm-*").stdout)

    assert rows == [
        {
            "name": "lightning-ai/glm-5.3",
            "provider": "lightning-ai",
            "display_name": "GLM-5.3",
            "status": "ONLINE",
            "context_length": 131072,
            "max_completion_tokens": 8192,
            "prompt_usd_per_1m_tokens": 2.0,
            "completion_usd_per_1m_tokens": 4.4,
        }
    ]


@pytest.mark.parametrize("key", LIST_KEYS)
@mock_command_logging
def test_llm_list_every_sort_key_also_filters(published_llm_endpoints, key) -> None:
    """Each key must work for both options against a real field, not just be accepted by the parser."""
    sorted_rows = json.loads(run_cli(f"lightning llm list --json --sort-by {key}").stdout)
    filtered_rows = json.loads(run_cli(f"lightning llm list --json --filter {key}=*").stdout)

    assert len(sorted_rows) == len(filtered_rows) == 5


@mock_command_logging
def test_llm_list_rejects_unknown_filter_key(published_llm_endpoints) -> None:
    result = CliRunner().invoke(list_llms, ["--filter", "price=1"])

    assert result.exit_code != 0
    assert "unknown key 'price'" in result.output
