import pytest

import lightning_sdk.api.lightning_storage_upload as lightning_storage_upload_module


def test_copy_local_file_to_lightning_storage_root_appends_basename(tmp_path, monkeypatch):
    local_file = tmp_path / "requests.csv"
    local_file.write_text("ok")
    upload_calls = []

    def fake_resolve(**kwargs):
        return lightning_storage_upload_module.LightningStorageUploadTarget(
            data_connection_id="dc-id",
            cloud_account="cluster-id",
            folder_name="exports",
            relative_parts=(),
        )

    def fake_upload(**kwargs):
        upload_calls.append(kwargs)
        upload_target = kwargs["upload_target"]
        destination_parts = kwargs["destination_parts"]
        return upload_target.absolute_path(*destination_parts)

    monkeypatch.setattr(
        lightning_storage_upload_module,
        "_resolve_lightning_storage_upload_target_from_parts",
        lambda **kwargs: fake_resolve(**kwargs),
    )
    monkeypatch.setattr(
        lightning_storage_upload_module,
        "upload_file_to_resolved_lightning_storage_target",
        fake_upload,
    )

    uploaded_paths = lightning_storage_upload_module.copy_local_path_to_lightning_storage(
        client=object(),
        teamspace_id="teamspace-id",
        local_path=local_file,
        remote_path="lightning_storage/exports",
    )

    assert uploaded_paths == ["/teamspace/lightning_storage/exports/requests.csv"]
    assert upload_calls[0]["destination_parts"] == ("requests.csv",)


def test_copy_local_file_to_lightning_storage_normalizes_windows_style_directory_target(tmp_path, monkeypatch):
    local_file = tmp_path / "requests.csv"
    local_file.write_text("ok")
    upload_calls = []

    def fake_resolve(**kwargs):
        return lightning_storage_upload_module.LightningStorageUploadTarget(
            data_connection_id="dc-id",
            cloud_account="cluster-id",
            folder_name="exports",
            relative_parts=(),
        )

    def fake_upload(**kwargs):
        upload_calls.append(kwargs)
        upload_target = kwargs["upload_target"]
        destination_parts = kwargs["destination_parts"]
        return upload_target.absolute_path(*destination_parts)

    monkeypatch.setattr(
        lightning_storage_upload_module,
        "_resolve_lightning_storage_upload_target_from_parts",
        lambda **kwargs: fake_resolve(**kwargs),
    )
    monkeypatch.setattr(
        lightning_storage_upload_module,
        "upload_file_to_resolved_lightning_storage_target",
        fake_upload,
    )

    uploaded_paths = lightning_storage_upload_module.copy_local_path_to_lightning_storage(
        client=object(),
        teamspace_id="teamspace-id",
        local_path=local_file,
        remote_path="lightning_storage\\exports\\",
    )

    assert uploaded_paths == ["/teamspace/lightning_storage/exports/requests.csv"]
    assert upload_calls[0]["destination_parts"] == ("requests.csv",)


def test_copy_local_file_to_lightning_storage_exact_remote_file_path(tmp_path, monkeypatch):
    local_file = tmp_path / "requests.csv"
    local_file.write_text("ok")
    upload_calls = []

    def fake_resolve(**kwargs):
        return lightning_storage_upload_module.LightningStorageUploadTarget(
            data_connection_id="dc-id",
            cloud_account="cluster-id",
            folder_name="exports",
            relative_parts=("daily",),
        )

    def fake_upload(**kwargs):
        upload_calls.append(kwargs)
        upload_target = kwargs["upload_target"]
        destination_parts = kwargs["destination_parts"]
        return upload_target.absolute_path(*destination_parts)

    monkeypatch.setattr(
        lightning_storage_upload_module,
        "_resolve_lightning_storage_upload_target_from_parts",
        lambda **kwargs: fake_resolve(**kwargs),
    )
    monkeypatch.setattr(
        lightning_storage_upload_module,
        "upload_file_to_resolved_lightning_storage_target",
        fake_upload,
    )

    uploaded_paths = lightning_storage_upload_module.copy_local_path_to_lightning_storage(
        client=object(),
        teamspace_id="teamspace-id",
        local_path=local_file,
        remote_path="lightning_storage/exports/daily/renamed.csv",
    )

    assert uploaded_paths == ["/teamspace/lightning_storage/exports/daily/renamed.csv"]
    assert upload_calls[0]["destination_parts"] == ("renamed.csv",)


def test_copy_local_file_to_lightning_storage_uses_ambiguous_leaf_as_explicit_filename(tmp_path, monkeypatch):
    local_file = tmp_path / "requests.csv"
    local_file.write_text("ok")
    upload_calls = []

    def fake_resolve(**kwargs):
        return lightning_storage_upload_module.LightningStorageUploadTarget(
            data_connection_id="dc-id",
            cloud_account="cluster-id",
            folder_name="exports",
            relative_parts=(),
        )

    def fake_upload(**kwargs):
        upload_calls.append(kwargs)
        upload_target = kwargs["upload_target"]
        destination_parts = kwargs["destination_parts"]
        return upload_target.absolute_path(*destination_parts)

    monkeypatch.setattr(
        lightning_storage_upload_module,
        "_resolve_lightning_storage_upload_target_from_parts",
        lambda **kwargs: fake_resolve(**kwargs),
    )
    monkeypatch.setattr(
        lightning_storage_upload_module,
        "upload_file_to_resolved_lightning_storage_target",
        fake_upload,
    )

    uploaded_paths = lightning_storage_upload_module.copy_local_path_to_lightning_storage(
        client=object(),
        teamspace_id="teamspace-id",
        local_path=local_file,
        remote_path="lightning_storage/exports/daily",
    )

    assert uploaded_paths == ["/teamspace/lightning_storage/exports/daily"]
    assert upload_calls[0]["destination_parts"] == ("daily",)


def test_copy_local_directory_requires_recursive(tmp_path):
    local_dir = tmp_path / "requests"
    local_dir.mkdir()

    with pytest.raises(ValueError, match="recursive=True"):
        lightning_storage_upload_module.copy_local_path_to_lightning_storage(
            client=object(),
            teamspace_id="teamspace-id",
            local_path=local_dir,
            remote_path="lightning_storage/exports",
            recursive=False,
        )


def test_copy_local_directory_to_lightning_storage_preserves_relative_paths(tmp_path, monkeypatch):
    local_dir = tmp_path / "requests"
    (local_dir / "nested").mkdir(parents=True)
    (local_dir / "top.csv").write_text("top")
    (local_dir / "nested" / "child.jsonl").write_text("child")
    upload_calls = []

    upload_target = lightning_storage_upload_module.LightningStorageUploadTarget(
        data_connection_id="dc-id",
        cloud_account="cluster-id",
        folder_name="exports",
        relative_parts=("daily",),
    )

    def fake_upload(**kwargs):
        upload_calls.append(kwargs)
        target = kwargs["upload_target"]
        destination_parts = kwargs["destination_parts"]
        return target.absolute_path(*destination_parts)

    monkeypatch.setattr(
        lightning_storage_upload_module,
        "resolve_lightning_storage_upload_target",
        lambda **kwargs: upload_target,
    )
    monkeypatch.setattr(
        lightning_storage_upload_module,
        "upload_file_to_resolved_lightning_storage_target",
        fake_upload,
    )

    uploaded_paths = lightning_storage_upload_module.copy_local_path_to_lightning_storage(
        client=object(),
        teamspace_id="teamspace-id",
        local_path=local_dir,
        remote_path="lightning_storage/exports/daily",
        recursive=True,
    )

    assert uploaded_paths == [
        "/teamspace/lightning_storage/exports/daily/nested/child.jsonl",
        "/teamspace/lightning_storage/exports/daily/top.csv",
    ]
    assert [call["destination_parts"] for call in upload_calls] == [
        ("nested", "child.jsonl"),
        ("top.csv",),
    ]


def test_copy_local_directory_to_lightning_storage_respects_progress_bar(tmp_path, monkeypatch):
    local_dir = tmp_path / "requests"
    local_dir.mkdir()
    (local_dir / "top.csv").write_text("top")
    upload_calls = []

    upload_target = lightning_storage_upload_module.LightningStorageUploadTarget(
        data_connection_id="dc-id",
        cloud_account="cluster-id",
        folder_name="exports",
        relative_parts=(),
    )

    def fake_upload(**kwargs):
        upload_calls.append(kwargs)
        target = kwargs["upload_target"]
        destination_parts = kwargs["destination_parts"]
        return target.absolute_path(*destination_parts)

    monkeypatch.setattr(
        lightning_storage_upload_module,
        "resolve_lightning_storage_upload_target",
        lambda **kwargs: upload_target,
    )
    monkeypatch.setattr(
        lightning_storage_upload_module,
        "upload_file_to_resolved_lightning_storage_target",
        fake_upload,
    )

    lightning_storage_upload_module.copy_local_path_to_lightning_storage(
        client=object(),
        teamspace_id="teamspace-id",
        local_path=local_dir,
        remote_path="lightning_storage/exports",
        recursive=True,
        progress_bar=True,
    )

    assert upload_calls[0]["progress_bar"] is True


@pytest.mark.parametrize("invalid_part", ["/escape", "..", "nested/child", r"nested\\child"])
def test_lightning_storage_upload_target_rejects_invalid_remote_parts(invalid_part):
    upload_target = lightning_storage_upload_module.LightningStorageUploadTarget(
        data_connection_id="dc-id",
        cloud_account="cluster-id",
        folder_name="exports",
        relative_parts=("daily",),
    )

    with pytest.raises(ValueError, match="Remote path parts"):
        upload_target.remote_path(invalid_part)


def test_parse_lightning_storage_path_rejects_parent_after_windows_separator_normalization():
    with pytest.raises(ValueError, match=r"must not be '\.\.'"):
        lightning_storage_upload_module._parse_lightning_storage_path("lightning_storage\\exports\\..\\daily")
