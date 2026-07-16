from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def test_job_example_documents_placement_metadata() -> None:
    source = (EXAMPLES_DIR / "jobs.py").read_text()

    assert "--placement-group-id" in source
    assert "placement_group_id=args.placement_group_id" in source
    assert "job.resource_id" in source
    assert "job.private_ip_address" in source
    assert "job.placement_group_id" in source


def test_mmt_example_documents_ranked_worker_metadata() -> None:
    source = (EXAMPLES_DIR / "mmts.py").read_text()

    assert "--placement-group-id" in source
    assert "placement_group_id=args.placement_group_id" in source
    assert "mmt.placement_group_id" in source
    assert "worker.rank" in source
    assert "worker.resource_id" in source
    assert "worker.private_ip_address" in source


def test_studio_example_documents_placement_metadata() -> None:
    source = (EXAMPLES_DIR / "studios.py").read_text()

    assert "studio.placement_group_id" in source
