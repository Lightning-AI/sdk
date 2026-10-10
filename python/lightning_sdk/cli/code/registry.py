"""The coding tools `lightning code` can set up, by the name the commands take."""

from lightning_sdk.cli.code.codex import Codex
from lightning_sdk.cli.code.cursor import Cursor
from lightning_sdk.cli.code.dsh import DeepSeekHarness
from lightning_sdk.cli.code.opencode import OpenCode
from lightning_sdk.cli.code.pi import Pi
from lightning_sdk.cli.code.tool import Tool

TOOLS: dict[str, Tool] = {tool.id: tool for tool in (OpenCode(), Pi(), Codex(), DeepSeekHarness(), Cursor())}
TOOL_NAMES = tuple(TOOLS)
