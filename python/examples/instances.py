#!/usr/bin/env python3
"""Executable SDK examples for Lightning cloud instances (plain VMs)."""

from __future__ import annotations

import argparse

from lightning_sdk import CloudInstance


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", default=None, help="Organization owning the instance.")

    subcommands = parser.add_subparsers(dest="example", required=True)

    create = subcommands.add_parser("create", help="Create an instance, run a command on it, and delete it.")
    create.add_argument("--name", default="sdk-tutorial-vm", help="Instance name.")
    create.add_argument("--instance-type", default="cpu-4", help="Machine type, see `lightning instance types`.")

    subcommands.add_parser("inspect", help="List instances and the machine types available to them.")

    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.example == "create":
        # sdk-instance-create-start
        instance = CloudInstance.create(
            name=args.name,
            instance_type=args.instance_type,
            org=args.org,
            # every port the instance should expose besides SSH
            ports=[8080],
            wait=True,
        )

        print(f"Instance {instance.name}: {instance.id} ({instance.status})")
        print(instance.ssh_command)

        # run a command over SSH with the Lightning-managed key
        instance.ssh("uname -a")

        instance.delete()
        # sdk-instance-create-end
    elif args.example == "inspect":
        # sdk-instance-inspect-start
        for instance_type in CloudInstance.instance_types(org=args.org):
            print(f"{instance_type.name:<24} {instance_type.description:<38} ${instance_type.cost:.2f}/h")

        for instance in CloudInstance.list(org=args.org):
            print(instance.to_dict())
        # sdk-instance-inspect-end


if __name__ == "__main__":
    main()
