from unittest import mock

import pytest

from lightning_sdk.api.utils import _RemoteApiError
from lightning_sdk.filesystem import Filesystem

TEAMSPACE_ID = "ts-123"
FAKE_AUTH_HEADERS = {"Authorization": "Bearer fake-token"}
HOST = "https://lightning.ai"
REMOTE_PATH = "data/model.ckpt"
LIT_URL = f"lit://my-org/my-teamspace/{REMOTE_PATH}"
LOCAL_PATH = "local/model.ckpt"


@pytest.fixture()
def fake_teamspace():
    ts = mock.MagicMock()
    ts.id = TEAMSPACE_ID
    return ts


@pytest.fixture()
def fake_path_result():
    return {
        "teamspace": "my-teamspace",
        "owner": "my-org",
        "destination": REMOTE_PATH,
    }


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.utils.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_auth_headers")
@mock.patch("lightning_sdk.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.parse_lit_url")
def test_copy_download_file(
    mock_parse_lit_url, mock_resolve, mock_authenticate, mock_client_cls, mock_get, fake_teamspace, tmp_path
):
    remote_path = "data/model.ckpt"
    mock_parse_lit_url.return_value = {
        "teamspace": "my-teamspace",
        "owner": "my-org",
        "destination": remote_path,
    }
    mock_resolve.return_value = fake_teamspace
    mock_authenticate.return_value = FAKE_AUTH_HEADERS
    mock_client_cls.return_value.api_client.configuration.host = HOST

    def fake_get(url, **kwargs):
        resp = mock.MagicMock()
        resp.status_code = 200
        if "trees" in url:
            resp.json.return_value = {"tree": [{"path": "data/model.ckpt", "type": "blob", "size": 1024}]}
        else:
            resp.headers = {"content-length": "1024"}
            resp.iter_content.side_effect = lambda *a, **kw: iter([b"x" * 1024])
        return resp

    mock_get.side_effect = fake_get

    # the download really writes to disk, so keep it inside tmp_path
    target = tmp_path / "model.ckpt"
    fs = Filesystem()
    fs.copy(LIT_URL, str(target))

    calls = [c[0][0] for c in mock_get.call_args_list]
    assert any("blobs" in url for url in calls)
    assert target.read_bytes() == b"x" * 1024


@mock.patch("lightning_sdk.api.filesystem_api._collect_download_results")
@mock.patch("lightning_sdk.api.filesystem_api.ThreadPoolExecutor")
@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.utils.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_auth_headers")
@mock.patch("lightning_sdk.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.parse_lit_url")
def test_copy_download_folder(
    mock_parse_lit_url,
    mock_resolve,
    mock_authenticate,
    mock_client_cls,
    mock_get,
    mock_executor,
    mock_collect,
    fake_teamspace,
    tmp_path,
):
    mock_parse_lit_url.return_value = {
        "teamspace": "my-teamspace",
        "owner": "my-org",
        "destination": "data/mydir",
    }
    mock_resolve.return_value = fake_teamspace
    mock_authenticate.return_value = FAKE_AUTH_HEADERS
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_collect.return_value = None

    def fake_get(url, **kwargs):
        resp = mock.MagicMock()
        resp.status_code = 200
        params = kwargs.get("params", {})
        if params.get("recursive") == "true":
            resp.json.return_value = {"tree": [{"path": "file1.txt", "type": "blob", "size": 500}]}
        else:
            resp.json.return_value = {"tree": [{"path": "data/mydir", "type": "tree", "size": 0}]}
        return resp

    mock_get.side_effect = fake_get

    # download_folder creates the target directory even with the executor mocked,
    # so keep it inside tmp_path
    fs = Filesystem()
    fs.copy("lit://my-org/my-teamspace/data/mydir", str(tmp_path / "local_out"), recursive=True)

    mock_executor.assert_called_once()
    mock_executor.return_value.__enter__.return_value.submit.assert_called()


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.utils.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_auth_headers", return_value=FAKE_AUTH_HEADERS)
@mock.patch("lightning_sdk.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.parse_lit_url")
def test_copy_raises_if_directory_without_recursive(
    mock_parse_lit_url, mock_resolve, _mock_authenticate, mock_client_cls, mock_get, fake_teamspace
):
    mock_parse_lit_url.return_value = {
        "teamspace": "my-teamspace",
        "owner": "my-org",
        "destination": "data/mydir",
    }
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"tree": [{"path": "mydir", "type": "tree", "size": 0}]}

    fs = Filesystem()
    with pytest.raises(ValueError, match="recursive=True"):
        fs.copy("lit://my-org/my-teamspace/data/mydir", "/tmp/local_out", recursive=False)


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.utils.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_auth_headers", return_value=FAKE_AUTH_HEADERS)
@mock.patch("lightning_sdk.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.parse_lit_url")
def test_copy_raises_if_remote_file_not_found(
    mock_parse_lit_url, mock_resolve, _mock_authenticate, mock_client_cls, mock_get, fake_teamspace, fake_path_result
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"tree": []}  # empty listing

    fs = Filesystem()
    with pytest.raises(ValueError, match="does not exist"):
        fs.copy(LIT_URL, LOCAL_PATH)


def test_copy_raises_if_both_remote():
    fs = Filesystem.__new__(Filesystem)
    with pytest.raises(ValueError, match="two remote URLs"):
        fs.copy("lit://org/ts/file.txt", "lit://org/ts/other.txt")


def test_copy_raises_if_both_local():
    fs = Filesystem.__new__(Filesystem)
    with pytest.raises(ValueError, match="At least one path"):
        fs.copy("/local/a.txt", "/local/b.txt")


def _upload_fs(fake_teamspace, destination):
    """A Filesystem with a mocked API, patched to resolve to fake_teamspace and destination."""
    fs = Filesystem.__new__(Filesystem)
    fs._filesystem_api = mock.Mock()
    patches = (
        mock.patch(
            "lightning_sdk.filesystem.parse_lit_url",
            return_value={"teamspace": "my-teamspace", "owner": "my-org", "destination": destination},
        ),
        mock.patch("lightning_sdk.filesystem.resolve_teamspace", return_value=fake_teamspace),
    )
    return fs, patches


def test_copy_upload_file_exact_remote_path(tmp_path, fake_teamspace):
    local = tmp_path / "model.ckpt"
    local.write_bytes(b"weights")

    fs, patches = _upload_fs(fake_teamspace, "lightning_storage/my-storage/data/model.ckpt")
    # the destination's parent holds no directory of that name -> explicit filename
    fs._filesystem_api.list_files.return_value = [{"path": "other", "type": "tree"}]

    with patches[0], patches[1]:
        fs.copy(str(local), "lit://my-org/my-teamspace/lightning_storage/my-storage/data/model.ckpt")

    fs._filesystem_api.upload_file.assert_called_once_with(
        teamspace_id=TEAMSPACE_ID,
        file_path=str(local),
        remote_path="lightning_storage/my-storage/data/model.ckpt",
        progress_bar=True,
        cloud_account=None,
    )


def test_copy_upload_file_to_trailing_slash_directory(tmp_path, fake_teamspace):
    local = tmp_path / "model.ckpt"
    local.write_bytes(b"weights")

    fs, patches = _upload_fs(fake_teamspace, "lightning_storage/my-storage/data/")

    with patches[0], patches[1]:
        fs.copy(str(local), "lit://my-org/my-teamspace/lightning_storage/my-storage/data/")

    # trailing slash means directory target; no listing round-trip needed
    fs._filesystem_api.list_files.assert_not_called()
    assert (
        fs._filesystem_api.upload_file.call_args.kwargs["remote_path"] == "lightning_storage/my-storage/data/model.ckpt"
    )


def test_copy_upload_file_into_existing_remote_directory(tmp_path, fake_teamspace):
    local = tmp_path / "model.ckpt"
    local.write_bytes(b"weights")

    fs, patches = _upload_fs(fake_teamspace, "lightning_storage/my-storage/data")
    fs._filesystem_api.list_files.return_value = [{"path": "data", "type": "tree"}]

    with patches[0], patches[1]:
        fs.copy(str(local), "lit://my-org/my-teamspace/lightning_storage/my-storage/data")

    fs._filesystem_api.list_files.assert_called_once_with(TEAMSPACE_ID, "lightning_storage/my-storage", recursive=False)
    assert (
        fs._filesystem_api.upload_file.call_args.kwargs["remote_path"] == "lightning_storage/my-storage/data/model.ckpt"
    )


def test_copy_upload_file_into_existing_remote_directory_with_qualified_tree_path(tmp_path, fake_teamspace):
    local = tmp_path / "model.ckpt"
    local.write_bytes(b"weights")

    fs, patches = _upload_fs(fake_teamspace, "lightning_storage/my-storage/data")
    fs._filesystem_api.list_files.return_value = [{"path": "lightning_storage/my-storage/data", "type": "tree"}]

    with patches[0], patches[1]:
        fs.copy(str(local), "lit://my-org/my-teamspace/lightning_storage/my-storage/data")

    assert (
        fs._filesystem_api.upload_file.call_args.kwargs["remote_path"] == "lightning_storage/my-storage/data/model.ckpt"
    )


def test_copy_upload_treats_unlistable_parent_as_explicit_filename(tmp_path, fake_teamspace):
    local = tmp_path / "file.txt"
    local.write_bytes(b"x")

    fs, patches = _upload_fs(fake_teamspace, "lightning_storage/new-folder/file.txt")
    fs._filesystem_api.list_files.side_effect = RuntimeError("Failed to list files: 404")

    with patches[0], patches[1]:
        fs.copy(str(local), "lit://my-org/my-teamspace/lightning_storage/new-folder/file.txt")

    assert fs._filesystem_api.upload_file.call_args.kwargs["remote_path"] == "lightning_storage/new-folder/file.txt"


def test_copy_upload_any_namespace_with_cloud_account(tmp_path, fake_teamspace):
    local = tmp_path / "data.csv"
    local.write_bytes(b"x")

    fs, patches = _upload_fs(fake_teamspace, "uploads/data.csv")
    fs._filesystem_api.list_files.return_value = []

    with patches[0], patches[1]:
        fs.copy(str(local), "lit://my-org/my-teamspace/uploads/data.csv", cloud_account="cluster-1")

    fs._filesystem_api.upload_file.assert_called_once_with(
        teamspace_id=TEAMSPACE_ID,
        file_path=str(local),
        remote_path="uploads/data.csv",
        progress_bar=True,
        cloud_account="cluster-1",
    )


def test_copy_upload_strips_teamspace_prefix(tmp_path, fake_teamspace):
    local = tmp_path / "file.txt"
    local.write_bytes(b"x")

    fs, patches = _upload_fs(fake_teamspace, "teamspace/lightning_storage/my-storage/file.txt")
    fs._filesystem_api.list_files.return_value = []

    with patches[0], patches[1]:
        fs.copy(str(local), "lit://my-org/my-teamspace/teamspace/lightning_storage/my-storage/file.txt")

    assert fs._filesystem_api.upload_file.call_args.kwargs["remote_path"] == "lightning_storage/my-storage/file.txt"


def test_copy_upload_directory_requires_recursive(tmp_path, fake_teamspace):
    (tmp_path / "a.txt").write_bytes(b"a")

    fs, patches = _upload_fs(fake_teamspace, "lightning_storage/my-storage/")

    with patches[0], patches[1], pytest.raises(ValueError, match="recursive=True"):
        fs.copy(str(tmp_path), "lit://my-org/my-teamspace/lightning_storage/my-storage/")


def test_copy_upload_directory_preserves_relative_paths(tmp_path, fake_teamspace):
    (tmp_path / "b.txt").write_bytes(b"b")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "a.txt").write_bytes(b"a")

    fs, patches = _upload_fs(fake_teamspace, "lightning_storage/my-storage/dest")

    with patches[0], patches[1]:
        fs.copy(str(tmp_path), "lit://my-org/my-teamspace/lightning_storage/my-storage/dest", recursive=True)

    uploaded = [call.kwargs["remote_path"] for call in fs._filesystem_api.upload_file.call_args_list]
    assert uploaded == [
        "lightning_storage/my-storage/dest/b.txt",
        "lightning_storage/my-storage/dest/nested/a.txt",
    ]


def test_copy_upload_missing_local_path_raises(fake_teamspace):
    fs, patches = _upload_fs(fake_teamspace, "lightning_storage/my-storage/file.txt")

    with patches[0], patches[1], pytest.raises(FileNotFoundError):
        fs.copy("does/not/exist", "lit://my-org/my-teamspace/lightning_storage/my-storage/file.txt")


_CLUSTER_REQUIRED_ERROR = _RemoteApiError(
    "Failed to request upload URLs for 'uploads/data.csv'. Status code: 400: "
    '{"error":"drive: invalid request: uploads require a ClusterID"}',
    status_code=400,
    server_message='{"error":"drive: invalid request: uploads require a ClusterID"}',
)


def test_copy_upload_falls_back_to_resolved_cloud_account(tmp_path, fake_teamspace):
    local = tmp_path / "data.csv"
    local.write_bytes(b"x")
    fake_teamspace._teamspace_api._determine_cloud_account.return_value = "default-cluster"

    fs, patches = _upload_fs(fake_teamspace, "uploads/data.csv")
    fs._filesystem_api.list_files.return_value = []
    fs._filesystem_api.upload_file.side_effect = [_CLUSTER_REQUIRED_ERROR, None]

    with patches[0], patches[1], pytest.warns(UserWarning, match="cloud account: default-cluster"):
        fs.copy(str(local), "lit://my-org/my-teamspace/uploads/data.csv")

    fake_teamspace._teamspace_api._determine_cloud_account.assert_called_once_with(fake_teamspace.id)
    accounts = [call.kwargs["cloud_account"] for call in fs._filesystem_api.upload_file.call_args_list]
    assert accounts == [None, "default-cluster"]


def test_copy_upload_directory_reuses_fallback_cloud_account(tmp_path, fake_teamspace):
    (tmp_path / "a.csv").write_bytes(b"a")
    (tmp_path / "b.csv").write_bytes(b"b")
    fake_teamspace._teamspace_api._determine_cloud_account.return_value = "default-cluster"

    fs, patches = _upload_fs(fake_teamspace, "uploads/dest")
    fs._filesystem_api.upload_file.side_effect = [_CLUSTER_REQUIRED_ERROR, None, None]

    with patches[0], patches[1], pytest.warns(UserWarning):
        fs.copy(str(tmp_path), "lit://my-org/my-teamspace/uploads/dest", recursive=True)

    accounts = [call.kwargs["cloud_account"] for call in fs._filesystem_api.upload_file.call_args_list]
    assert accounts == [None, "default-cluster", "default-cluster"]


def test_copy_upload_does_not_retry_other_errors(tmp_path, fake_teamspace):
    local = tmp_path / "data.csv"
    local.write_bytes(b"x")

    fs, patches = _upload_fs(fake_teamspace, "uploads/data.csv")
    fs._filesystem_api.list_files.return_value = []
    fs._filesystem_api.upload_file.side_effect = _RemoteApiError(
        "Failed to upload. Status code: 500", status_code=500, server_message="internal error"
    )

    with patches[0], patches[1], pytest.raises(RuntimeError, match="500"):
        fs.copy(str(local), "lit://my-org/my-teamspace/uploads/data.csv")

    assert fs._filesystem_api.upload_file.call_count == 1


def test_copy_upload_does_not_second_guess_an_explicit_cloud_account(tmp_path, fake_teamspace):
    local = tmp_path / "data.csv"
    local.write_bytes(b"x")

    fs, patches = _upload_fs(fake_teamspace, "uploads/data.csv")
    fs._filesystem_api.list_files.return_value = []
    fs._filesystem_api.upload_file.side_effect = _CLUSTER_REQUIRED_ERROR

    with patches[0], patches[1], pytest.raises(RuntimeError, match="require a ClusterID"):
        fs.copy(str(local), "lit://my-org/my-teamspace/uploads/data.csv", cloud_account="my-cluster")

    assert fs._filesystem_api.upload_file.call_count == 1


def test_copy_upload_errors_helpfully_when_no_cloud_account_resolves(tmp_path, fake_teamspace):
    local = tmp_path / "data.csv"
    local.write_bytes(b"x")
    fake_teamspace._teamspace_api._determine_cloud_account.side_effect = RuntimeError(
        "Could not determine the current cloud account. Please provide it manually as input."
    )

    fs, patches = _upload_fs(fake_teamspace, "uploads/data.csv")
    fs._filesystem_api.list_files.return_value = []
    fs._filesystem_api.upload_file.side_effect = _CLUSTER_REQUIRED_ERROR

    with patches[0], patches[1], pytest.raises(RuntimeError, match="Pass cloud_account"):
        fs.copy(str(local), "lit://my-org/my-teamspace/uploads/data.csv")


def test_copy_download_maps_missing_parent_to_does_not_exist(fake_teamspace):
    fs, patches = _upload_fs(fake_teamspace, "r2_connections/nope/file.txt")
    fs._filesystem_api.list_files.side_effect = _RemoteApiError("Failed to list files: 404", status_code=404)

    with patches[0], patches[1], pytest.raises(ValueError, match="does not exist in teamspace"):
        fs.copy("lit://my-org/my-teamspace/r2_connections/nope/file.txt", "/tmp/out")
