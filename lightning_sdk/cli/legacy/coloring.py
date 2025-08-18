from typing import Optional, Sequence, Tuple

from click.formatting import HelpFormatter, term_len, wrap_text
from click.termui import style


class CustomHelpFormatter(HelpFormatter):
    _primary = "magenta"
    _secondary = "cyan"

    def write_heading(self, heading: str) -> None:
        # Style the heading (command name) in cyan
        return super().write_heading(style(heading, fg=self._primary, bold=True))

    def write_usage(self, prog: str, args: str = "", prefix: Optional[str] = None) -> None:
        if prefix is None:
            prefix = "Usage: "

        styled_prefix = style(prefix, fg=self._primary, bold=True)
        styled_prog = style(prog, fg=self._secondary, bold=True)
        styled_args = style(args, fg=self._secondary, bold=True)

        # this is required because otherwise the super() call would include the special characters for coloring in the
        # width and indent computation leading to wrong results since these characters won't be displayed in the end.
        usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
        styled_usage_prefix = f"{styled_prefix:>{self.current_indent}}{styled_prog} "
        text_width = self.width - self.current_indent

        if text_width >= (term_len(usage_prefix) + 20):
            # The arguments will fit to the right of the prefix.
            self.write(styled_usage_prefix)
            indent = " " * term_len(usage_prefix)
            self.write(
                wrap_text(
                    styled_args,
                    text_width,
                    initial_indent="",
                    subsequent_indent=indent,
                )
            )
        else:
            # The prefix is too long, put the arguments on the next line.
            self.write(styled_usage_prefix)
            self.write("\n")
            indent = " " * (max(self.current_indent, term_len(prefix)) + 4)
            self.write(wrap_text(styled_args, text_width, initial_indent=indent, subsequent_indent=indent))

        self.write("\n")

    def write_dl(
        self,
        rows: Sequence[Tuple[str, str]],
        col_max: int = 30,
        col_spacing: int = 2,
    ) -> None:
        new_rows = []
        for row in rows:
            new_row = (style(row[0], fg=self._secondary, bold=True), row[1])
            new_rows.append(new_row)
        super().write_dl(new_rows, col_max=col_max, col_spacing=col_spacing)
