import os
from typing import Any

from rich.console import Console

from lightning_sdk.studio import Studio
from lightning_sdk.utils.resolve import _get_studio_url


def rich_to_str(*renderables: Any) -> str:
    with open(os.devnull, "w") as f:
        console = Console(file=f, record=True)
        console.print(*renderables)
    return console.export_text(styles=True)


# not supported on all terminals (e.g. older ones). in that case it's a name without a link
# see https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda#hyperlinks-aka-html-like-anchors-in-terminal-emulators
# for details and
# https://github.com/Alhadis/OSC8-Adoption/blob/main/README.md for status of OSC8 adoption
def studio_name_link(studio: Studio, to_ascii: bool = True) -> str:
    """Hyperlink a studio name.

    Args:
      studio: the studio whose name to print and link to the studio url
      to_ascii: whether return a plain ascii string with characters for linking converted to ascii as well.
        if False, returns the rich markup directly.
    """
    url = _get_studio_url(studio)

    studio_link_markup = f"[link={url}]{studio.name}[/link]"
    if not to_ascii:
        return studio_link_markup

    return rich_to_str(studio_link_markup).strip("\n")
