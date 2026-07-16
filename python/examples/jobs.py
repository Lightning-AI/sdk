#!/usr/bin/env python3
"""Executable SDK examples for Lightning jobs."""

from __future__ import annotations

import argparse

from lightning_sdk import Job, Machine, Status, Studio, Teamspace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teamspace", required=True, help="Teamspace name without owner.")
    parser.add_argument("--org", help="Organization that owns the teamspace.")
    parser.add_argument("--user", help="User that owns the teamspace.")

    subcommands = parser.add_subparsers(dest="example", required=True)

    studio_job = subcommands.add_parser("studio", help="Run a Studio-backed job.")
    studio_job.add_argument("--studio", required=True, help="Existing Studio name.")
    studio_job.add_argument("--name", default="sdk-tutorial-job", help="Job name.")
    studio_job.add_argument("--machine", default="CPU", help="Machine type.")
    studio_job.add_argument("--command", default="python train.py --epochs 1", help="Command to run.")
    studio_job.add_argument(
        "--placement-group-id",
        help="Existing placement group to join, for example from a Studio or another Job.",
    )

    image_job = subcommands.add_parser("image", help="Run a container-backed job.")
    image_job.add_argument("--name", default="sdk-image-job", help="Job name.")
    image_job.add_argument("--machine", default="CPU", help="Machine type.")
    image_job.add_argument("--image", default="python:3.11-slim", help="Docker image.")
    image_job.add_argument(
        "--placement-group-id",
        help="Existing placement group to join, for example from a Studio or another Job.",
    )
    image_job.add_argument(
        "--command",
        default="python -c 'print(\"hello from a Lightning job\")'",
        help="Command to run.",
    )

    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.example == "studio":
        # sdk-studio-job-start
        teamspace = Teamspace(args.teamspace, org=args.org, user=args.user)
        studio = Studio(args.studio, teamspace=teamspace, create_ok=False)

        job = Job.run(
            name=args.name,
            teamspace=teamspace,
            studio=studio,
            machine=Machine.from_str(args.machine),
            env={"RUN_MODE": "tutorial"},
            command=args.command,
            placement_group_id=args.placement_group_id,
        )

        print(f"Job link: {job.link}")
        job.wait(interval=10, timeout=60 * 60, stop_on_timeout=True)

        print(job.json())
        print(f"Job resource id: {job.resource_id}")
        print(f"Job private IP: {job.private_ip_address}")
        print(f"Job placement group: {job.placement_group_id}")
        if job.status == Status.Failed:
            print(job.logs)
        # sdk-studio-job-end
    elif args.example == "image":
        # sdk-image-job-start
        teamspace = Teamspace(args.teamspace, org=args.org, user=args.user)

        job = Job.run(
            name=args.name,
            teamspace=teamspace,
            image=args.image,
            machine=Machine.from_str(args.machine),
            command=args.command,
            env={"RUN_MODE": "tutorial"},
            interruptible=True,
            placement_group_id=args.placement_group_id,
        )

        job.wait(interval=10)
        print(f"{job.name} finished with status {job.status}")
        print(f"Job resource id: {job.resource_id}")
        print(f"Job private IP: {job.private_ip_address}")
        print(f"Job placement group: {job.placement_group_id}")
        # sdk-image-job-end


if __name__ == "__main__":
    main()
