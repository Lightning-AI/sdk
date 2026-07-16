"""Structured Click command reference rendering for the CLI documentation."""

from __future__ import annotations

import inspect

import click
from click_extra.sphinx.click import TreeDirective
from docutils import nodes
from docutils.statemachine import StringList


def _clean_text(value: str | None) -> str:
    """Return a compact description for a command or parameter."""
    if not value:
        return "No description provided."
    return " ".join(inspect.cleandoc(value).split())


def _display_default(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return str(value).lower()
    return repr(value)


def _literal(value: object, rst: bool) -> str:
    marker = "``" if rst else "`"
    return f"{marker}{value}{marker}"


def _display_type(param: click.Parameter, context: click.Context) -> str:
    """Get the Click metavar without depending on a Click minor version."""
    for getter in (
        lambda: param.make_metavar(context),
        lambda: param.make_metavar(),
        lambda: param.type.get_metavar(param, context),
        lambda: param.type.name,
    ):
        try:
            value = getter()
        except (AttributeError, TypeError):
            continue
        if value:
            return str(value)
    return "—"


def _split_help(value: str | None) -> tuple[list[str], list[str]]:
    """Separate command prose from its documented examples."""
    text = inspect.cleandoc(value or "").strip()
    if not text:
        return [], []

    lines = text.splitlines()
    example_index = next(
        (index for index, line in enumerate(lines) if line.strip().lower() in {"example:", "examples:"}),
        None,
    )
    if example_index is None:
        return lines, []

    description = lines[:example_index]
    while description and not description[-1].strip():
        description.pop()

    examples = [line[2:] if line.startswith("  ") else line for line in lines[example_index + 1 :]]
    while examples and not examples[-1].strip():
        examples.pop()
    return description, examples


def _parameter_rows(
    command: click.Command,
    context: click.Context,
    rst: bool,
) -> tuple[list[list[str]], list[list[str]]]:
    arguments: list[list[str]] = []
    options: list[list[str]] = []

    for param in command.params:
        # Every command answers --help identically, so a row for it on each
        # Options table is repeated noise — omit it throughout.
        if isinstance(param, click.Option) and "--help" in param.opts:
            continue
        description = _clean_text(getattr(param, "help", None))
        if isinstance(param, click.Argument):
            # An argument's metavar just repeats its name, so show the Click
            # type (text, path, integer, ...) instead.
            arguments.append(
                [
                    _literal(param.name.upper(), rst),
                    _literal(param.type.name or "text", rst),
                    "yes" if param.required else "no",
                    description,
                ],
            )
            continue

        if isinstance(param, click.Option):
            names = [*param.opts, *param.secondary_opts]
            options.append(
                [
                    ", ".join(_literal(name, rst) for name in names),
                    _literal(_display_type(param, context), rst) if not param.is_flag else "—",
                    "yes" if param.required else "no",
                    # A flag's implicit false default carries no information.
                    "—"
                    if param.default is None or (param.is_flag and param.default is False)
                    else _literal(_display_default(param.default), rst),
                    description,
                ],
            )

    return arguments, options


def _command_link(name: str, anchor: str) -> nodes.paragraph:
    """A table cell linking a command's name to its section on this page."""
    paragraph = nodes.paragraph()
    link = nodes.reference(refuri=f"#{anchor}")
    link += nodes.literal(text=name)
    paragraph += link
    return paragraph


def _append_table(
    directive: ReferenceDirective,
    parent: nodes.Element,
    headers: list[str],
    rows: list[list[str]],
    source_file: str,
) -> None:
    table = nodes.table(classes=["colwidths-auto"])
    tgroup = nodes.tgroup(cols=len(headers))
    table += tgroup
    for _ in headers:
        tgroup += nodes.colspec(colwidth=1)

    def add_row(container: nodes.Element, values: list[str | nodes.Node]) -> None:
        row = nodes.row()
        for value in values:
            entry = nodes.entry()
            if isinstance(value, nodes.Node):
                entry += value
            else:
                directive.state.nested_parse(StringList([value], source_file), 0, entry)
            row += entry
        container += row

    thead = nodes.thead()
    add_row(thead, headers)
    tgroup += thead
    tbody = nodes.tbody()
    for row in rows:
        add_row(tbody, row)
    tgroup += tbody
    parent += table


class ReferenceDirective(TreeDirective):
    """Render Click metadata as a structured API-style reference."""

    def run(self) -> list[nodes.Node]:
        if self.content:
            self.runner.execute_source(self)

        cli_expr = self.arguments[0].strip()
        try:
            cli = eval(cli_expr, self.runner.namespace)
        except Exception as exc:
            raise RuntimeError(
                f"lightning-reference: failed to evaluate {cli_expr!r}: {exc}",
            ) from exc
        if not isinstance(cli, click.Command):
            raise TypeError(
                f"lightning-reference: {cli_expr!r} did not yield a click.Command (got {type(cli).__name__}).",
            )

        max_depth = self.options.get("max-depth", 10)
        root_label = self.options.get("root-label") or cli.name or cli_expr
        anchor_prefix = self.options.get("anchor-prefix") or self._slug(root_label)
        root_parts = root_label.split()
        entries = self._walk(cli, max_depth)
        source_file, _ = self.get_source_info()
        # A container (not a section): the page's own title already names the
        # root command, so the root gets no heading of its own — and a title-less
        # section would leak its first paragraph into the page toc. The class lets
        # downstream stylesheets target CLI reference pages without content-sniffing.
        # Child sections are hoisted out on return (see below).
        root_section = nodes.container(ids=[anchor_prefix], classes=["cli-reference"])
        command_sections: dict[tuple[str, ...], nodes.Element] = {(): root_section}

        for path, command in [([], cli), *entries]:
            anchor = "-".join([anchor_prefix, *(self._slug(part) for part in path)])
            label = " ".join([root_label, *path])
            full_path = [*root_parts, *path]
            context = click.Context(command, info_name=" ".join(full_path))
            if path:
                command_section = nodes.section(ids=[anchor])
                command_sections[tuple(path[:-1])] += command_section
                command_sections[tuple(path)] = command_section
                command_section += nodes.title(text=label)
            else:
                command_section = root_section

            description, examples = _split_help(command.help)
            if description:
                self.state.nested_parse(StringList(description, source_file), 0, command_section)

            usage = " ".join(command.collect_usage_pieces(context))
            usage = " ".join([*full_path, usage]).strip()
            if usage:
                # A literal block (rather than an inline literal) so themes give
                # the synopsis code-block treatment: highlighting + a copy button.
                label = nodes.paragraph()
                label += nodes.strong(text="Usage:")
                command_section += label
                command_section += nodes.literal_block(usage, usage, language="console")

            if isinstance(command, click.Group) and command.commands:
                # "Commands" matches Click's own vocabulary: the usage line says
                # `COMMAND [ARGS]...` and Click's help prints a "Commands" section.
                commands_section = nodes.section(ids=[f"{anchor}-commands"])
                commands_section += nodes.title(text="Commands")
                rows = [
                    [
                        _command_link(name, f"{anchor}-{self._slug(name)}"),
                        _clean_text(subcommand.get_short_help_str(limit=200)),
                    ]
                    for name, subcommand in sorted(command.commands.items())
                ]
                _append_table(self, commands_section, ["Command", "Description"], rows, source_file)
                command_section += commands_section

            arguments, options = _parameter_rows(command, context, True)
            if arguments:
                arguments_section = nodes.section(ids=[f"{anchor}-arguments"])
                arguments_section += nodes.title(text="Arguments")
                _append_table(
                    self,
                    arguments_section,
                    ["Name", "Type", "Required", "Description"],
                    arguments,
                    source_file,
                )
                command_section += arguments_section
            if options:
                options_section = nodes.section(ids=[f"{anchor}-options"])
                options_section += nodes.title(text="Options")
                _append_table(
                    self,
                    options_section,
                    ["Option", "Type", "Required", "Default", "Description"],
                    options,
                    source_file,
                )
                command_section += options_section
            if examples:
                examples_section = nodes.section(ids=[f"{anchor}-examples"])
                examples_section += nodes.title(text="Examples")
                examples_section += nodes.literal_block(
                    "\n".join(examples),
                    "\n".join(examples),
                    language="console",
                )
                command_section += examples_section

        # Hoist the root's child sections (Commands, each subcommand, ...) to
        # document level: Sphinx's page toc only descends through sections, so
        # anything left inside the container would vanish from "On this page".
        result: list[nodes.Node] = [root_section]
        for child in list(root_section.children):
            if isinstance(child, nodes.section):
                root_section.remove(child)
                result.append(child)
        return result
