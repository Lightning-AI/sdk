#!/usr/bin/env python3
"""Executable SDK examples for Lightning Studios."""

from __future__ import annotations

import argparse

from lightning_sdk import Machine, Studio, Teamspace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teamspace", required=True, help="Teamspace name without owner.")
    parser.add_argument("--org", help="Organization that owns the teamspace.")
    parser.add_argument("--user", help="User that owns the teamspace.")
    parser.add_argument("--studio", default="sdk-tutorial-studio", help="Studio name.")
    parser.add_argument("--machine", default="CPU", help="Machine type.")
    parser.add_argument("--train-file", default="train.py", help="Local file to upload and run.")
    parser.add_argument("--run-tests", action="store_true", help="Run pytest and check the exit code.")
    parser.add_argument("--detach-training", action="store_true", help="Start a longer training command.")
    return parser


def main() -> None:
    args = _parser().parse_args()
    # sdk-studio-workflow-start
    teamspace = Teamspace(args.teamspace, org=args.org, user=args.user)

    studio = Studio(
        name=args.studio,
        teamspace=teamspace,
        create_ok=True,
    )

    studio.start(machine=Machine.from_str(args.machine))
    print(f"{studio.name} is {studio.status} on {studio.machine}")
    print(f"Studio placement group: {studio.placement_group_id}")

    output = studio.run("python --version")
    print(output)

    studio.upload_file(args.train_file, remote_path="train.py")
    train_output = studio.run("python train.py --epochs 1")
    print(train_output)
    # sdk-studio-workflow-end

    # sdk-studio-exit-code-start
    if args.run_tests:
        output, exit_code = studio.run_with_exit_code("python -m pytest -q")
        print(output)
        if exit_code != 0:
            raise RuntimeError(f"Tests failed with exit code {exit_code}")
    # sdk-studio-exit-code-end

    # sdk-studio-detach-start
    if args.detach_training:
        output, exit_code = studio.run_and_detach(
            "python train.py --epochs 10",
            timeout=30,
            check_interval=5,
        )
        print(output)
        print(f"Initial exit code: {exit_code}")
    # sdk-studio-detach-end

    studio.stop()


if __name__ == "__main__":
    main()
