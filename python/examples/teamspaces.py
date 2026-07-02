#!/usr/bin/env python3
"""Executable SDK examples for Lightning teamspaces."""

from __future__ import annotations

import argparse
import os

from lightning_sdk import Job, Machine, SecretType, Studio, Teamspace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teamspace", required=True, help="Teamspace name without owner.")
    parser.add_argument("--org", help="Organization that owns the teamspace.")
    parser.add_argument("--user", help="User that owns the teamspace.")

    subcommands = parser.add_subparsers(dest="example", required=True)
    subcommands.add_parser("inspect", help="Inspect teamspace metadata and resources.")

    job = subcommands.add_parser("job", help="Run a teamspace-scoped job.")
    job.add_argument("--studio", required=True, help="Existing Studio name.")

    subcommands.add_parser("set-secret", help="Set HF_TOKEN as a teamspace secret.")

    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.example == "inspect":
        # sdk-teamspace-inspect-start
        teamspace = Teamspace(args.teamspace, org=args.org, user=args.user)

        print(f"Teamspace: {teamspace.owner.name}/{teamspace.name}")
        print(f"ID: {teamspace.id}")
        print(f"Default cloud account: {teamspace.default_cloud_account}")
        print(f"Cloud accounts: {', '.join(teamspace.cloud_accounts)}")

        for studio in teamspace.studios:
            print(f"Studio {studio.name}: {studio.status}")

        for job in teamspace.jobs:
            print(f"Job {job.name}: {job.status} on {job.machine}")

        for mmt in teamspace.multi_machine_jobs:
            print(f"MMT {mmt.name}: {mmt.status} across {mmt.num_machines} machines")
        # sdk-teamspace-inspect-end
    elif args.example == "job":
        # sdk-teamspace-job-start
        teamspace = Teamspace(args.teamspace, org=args.org, user=args.user)
        studio = Studio(args.studio, teamspace=teamspace, create_ok=False)

        job = Job.run(
            name="teamspace-scoped-job",
            teamspace=teamspace,
            studio=studio,
            machine=Machine.CPU,
            command="python train.py --epochs 1",
        )

        print(job.link)
        # sdk-teamspace-job-end
    elif args.example == "set-secret":
        # sdk-teamspace-secret-start
        teamspace = Teamspace(args.teamspace, org=args.org, user=args.user)
        teamspace.set_secret(
            key="HF_TOKEN_FOR_TUTORIAL",
            value=os.environ["HF_TOKEN"],
            secret_type=SecretType.HF_TOKEN,
        )
        # sdk-teamspace-secret-end


if __name__ == "__main__":
    main()
