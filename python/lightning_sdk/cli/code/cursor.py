"""Cursor: create a key and print the steps to add it in Cursor Settings.

Cursor keeps these settings in an internal database it holds open and rewrites, with the
key encrypted through the OS keychain, so nothing outside it can set them safely. Its
`cursor-agent` CLI only runs Cursor's own models.
"""

from typing import Optional, Sequence

from lightning_sdk.cli.code import files
from lightning_sdk.cli.code.models import CODE_BASE_URL, CodingModel, default_model
from lightning_sdk.cli.code.tool import KeyRecord, Plan, Tool, ToolState, record_change


class Cursor(Tool):
    id = "cursor"
    name = "Cursor"
    start = ""

    def read(self) -> ToolState:
        # Cursor's copy of the key can't be read back, so every setup creates a new one
        record = KeyRecord.from_dict(files.load_record(self.id))
        return ToolState(
            record=record,
            key=None,
            configured=record is not None,
            default_model=None,
            location="Cursor Settings > Models",
        )

    def plan_setup(
        self,
        state: ToolState,
        *,
        models: Sequence[CodingModel],
        model: Optional[str],
        key: str,
        record: KeyRecord,
    ) -> Plan:
        return Plan(changes=[record_change(self.id, record)])

    def plan_remove(self, state: ToolState) -> Plan:
        plan = Plan(changes=[record_change(self.id, None)])
        if state.record is not None:
            plan.removed.append("the record of Cursor's key")
        return plan

    def instructions(self, key: str, models: Sequence[CodingModel], plan: Plan) -> Optional[str]:
        names = "\n".join(f"       {m.id}" for m in models)
        first = default_model(tuple(models))
        first_id = next(m.id for m in models if m.key == first)
        return f"""Finish in Cursor (needs a paid Cursor plan):
  1. Open Cursor Settings (Cmd+Shift+J on macOS, Ctrl+Shift+J elsewhere) and go to Models.
  2. Under API Keys, paste this into OpenAI API Key and press Enter:
       {key}
  3. Turn on "Use OpenAI API Key".
  4. Turn on "Override OpenAI Base URL" and enter:
       {CODE_BASE_URL}
  5. At the top of Models, add these model names and make sure they're switched on:
{names}
  6. Open a new chat and pick {first_id}.

The key is shown only this once. While the base URL override is on, Cursor sends all
OpenAI models to Lightning, so its own GPT and Auto models stop working; turn the
override off to switch back. Tab completion keeps using Cursor's models, and the
cursor-agent CLI can't use Lightning models."""

    def removal_instructions(self) -> Optional[str]:
        return (
            'In Cursor Settings > Models, turn off "Override OpenAI Base URL" and "Use OpenAI API Key",\n'
            "and remove the Lightning model names."
        )
