#!/usr/bin/env python3
"""Executable SDK examples for Lightning sandboxes."""

from __future__ import annotations

import argparse

from lightning_sdk.sandbox import RunCommandOpts, Sandbox


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teamspace", required=True, help="Teamspace in owner/name format.")

    subcommands = parser.add_subparsers(dest="example", required=True)

    create = subcommands.add_parser("create", help="Create, run, and stop a sandbox.")
    create.add_argument("--name", default="sdk-tutorial-sandbox", help="Sandbox name.")
    create.add_argument("--instance-type", default="cpu-1", help="Sandbox instance type.")

    inspect = subcommands.add_parser("inspect", help="Inspect, resume, and delete a sandbox.")
    inspect.add_argument("--sandbox-id", required=True, help="Sandbox id.")

    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.example == "create":
        # sdk-sandbox-create-start
        sandbox = Sandbox.create(
            name=args.name,
            teamspace=args.teamspace,
            instance_type=args.instance_type,
            persistent=True,
        )

        print(f"Sandbox {sandbox.name}: {sandbox.sandbox_id}")

        sandbox.write_file(
            "/workspace/app.py",
            "print('hello from a file inside the sandbox')\n",
        )

        command = sandbox.run_command(
            RunCommandOpts(
                cmd="python",
                args=["/workspace/app.py"],
                env={"MODE": "tutorial"},
            )
        )
        print(command.output)

        auto_snapshot_id = sandbox.stop()
        print(f"Auto snapshot: {auto_snapshot_id}")
        # sdk-sandbox-create-end
    elif args.example == "inspect":
        # sdk-sandbox-client-start
        client = Sandbox()

        result = client.list(teamspace=args.teamspace, limit=10)
        for sandbox in result.sandboxes:
            print(f"{sandbox.sandbox_id}: {sandbox.name} ({sandbox.status})")

        sandbox = client.get(args.sandbox_id)
        if sandbox.status == "paused":
            sandbox = sandbox.resume()

        command = sandbox.run_command("python --version")
        print(command.output)

        sandbox.delete()
        # sdk-sandbox-client-end


if __name__ == "__main__":
    main()
