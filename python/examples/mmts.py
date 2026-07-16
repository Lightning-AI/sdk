#!/usr/bin/env python3
"""Executable SDK examples for Lightning multi-machine training."""

from __future__ import annotations

import argparse

from lightning_sdk import MMT, Machine, Status, Studio, Teamspace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teamspace", required=True, help="Teamspace name without owner.")
    parser.add_argument("--org", help="Organization that owns the teamspace.")
    parser.add_argument("--user", help="User that owns the teamspace.")

    subcommands = parser.add_subparsers(dest="example", required=True)

    studio_mmt = subcommands.add_parser("studio", help="Run a Studio-backed MMT.")
    studio_mmt.add_argument("--studio", required=True, help="Existing Studio name.")
    studio_mmt.add_argument("--name", default="sdk-tutorial-mmt", help="MMT name.")
    studio_mmt.add_argument("--num-machines", type=int, default=2, help="Number of machines.")
    studio_mmt.add_argument("--machine", default="CPU", help="Machine type.")
    studio_mmt.add_argument("--command", default="python train_distributed.py --epochs 1", help="Command to run.")
    studio_mmt.add_argument(
        "--placement-group-id",
        help="Existing placement group to join, for example from a Studio or Job.",
    )

    image_mmt = subcommands.add_parser("image", help="Run a container-backed MMT.")
    image_mmt.add_argument("--name", default="sdk-image-mmt", help="MMT name.")
    image_mmt.add_argument("--num-machines", type=int, default=2, help="Number of machines.")
    image_mmt.add_argument("--machine", default="L4", help="Machine type.")
    image_mmt.add_argument(
        "--placement-group-id",
        help="Existing placement group to join, for example from a Studio or Job.",
    )
    image_mmt.add_argument(
        "--image",
        default="pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime",
        help="Docker image.",
    )
    image_mmt.add_argument(
        "--command",
        default="python -m torch.distributed.run --nproc_per_node=1 train.py",
        help="Command to run.",
    )

    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.example == "studio":
        # sdk-studio-mmt-start
        teamspace = Teamspace(args.teamspace, org=args.org, user=args.user)
        studio = Studio(args.studio, teamspace=teamspace, create_ok=False)

        mmt = MMT.run(
            name=args.name,
            teamspace=teamspace,
            studio=studio,
            num_machines=args.num_machines,
            machine=Machine.from_str(args.machine),
            env={"RUN_MODE": "distributed"},
            command=args.command,
            placement_group_id=args.placement_group_id,
        )

        print(f"MMT link: {mmt.link}")
        mmt.wait(interval=15, timeout=2 * 60 * 60, stop_on_timeout=True)
        print(mmt.json())
        print(f"MMT placement group: {mmt.placement_group_id}")

        if mmt.status == Status.Failed:
            for worker in mmt.machines:
                print(f"Worker {worker.name}: {worker.status}")
        else:
            for worker in mmt.machines:
                print(
                    f"Worker rank={worker.rank} "
                    f"resource_id={worker.resource_id} "
                    f"private_ip={worker.private_ip_address}"
                )
        # sdk-studio-mmt-end
    elif args.example == "image":
        # sdk-image-mmt-start
        teamspace = Teamspace(args.teamspace, org=args.org, user=args.user)

        mmt = MMT.run(
            name=args.name,
            teamspace=teamspace,
            image=args.image,
            num_machines=args.num_machines,
            machine=Machine.from_str(args.machine),
            command=args.command,
            interruptible=True,
            placement_group_id=args.placement_group_id,
        )

        mmt.wait(interval=15)
        print(f"{mmt.name} used {mmt.num_machines} machines")
        print(f"MMT placement group: {mmt.placement_group_id}")
        for worker in mmt.machines:
            print(
                f"Worker rank={worker.rank} "
                f"resource_id={worker.resource_id} "
                f"private_ip={worker.private_ip_address}"
            )
        # sdk-image-mmt-end


if __name__ == "__main__":
    main()
