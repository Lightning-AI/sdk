import io
import json
import zipfile
from concurrent.futures import Future
from types import SimpleNamespace
from unittest import mock

import pytest

from lightning_sdk.datasets import download_dataset
from lightning_sdk.lightning_cloud.utils.dataset import (
    _download_dataset_files,
    _download_dataset_version,
)


class _RangeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=None):
        return iter([self.payload])


class _SyncExecutor:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def submit(self, function, *args, **kwargs):
        future = Future()
        try:
            future.set_result(function(*args, **kwargs))
        except Exception as ex:
            future.set_exception(ex)
        return future


def _mock_files_api(files):
    response = mock.MagicMock()
    response.data = json.dumps({"files": files})
    api_client = mock.MagicMock()
    api_client.request.return_value = response
    api_client.default_headers = {}
    client = mock.MagicMock()
    client.api_client = api_client
    return mock.patch("lightning_sdk.lightning_cloud.utils.dataset.LightningClient", return_value=client)


def _range_get(payloads):
    def get(url, headers=None, stream=None):
        start, end = (int(value) for value in headers["Range"].split("=")[1].split("-"))
        return _RangeResponse(payloads[url][start : end + 1])

    return get


def _zip_payload(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return output.getvalue()


@pytest.mark.parametrize(
    ("as_zip", "unzip", "expected_name"),
    [
        (False, False, "my-dataset_v7"),
        (True, False, "my-dataset_v7.zip"),
        (False, True, "my-dataset_v7"),
    ],
)
def test_download_dataset_output_mode_and_parallel_options(tmp_path, as_zip, unzip, expected_name):
    teamspace = SimpleNamespace(id="project-id")
    with (
        mock.patch("lightning_sdk.datasets._get_teamspace", return_value=teamspace),
        mock.patch("lightning_sdk.datasets.raise_access_error_if_not_allowed"),
        mock.patch(
            "lightning_sdk.datasets._resolve_dataset_id_and_version",
            return_value=("dataset-id", "v7"),
        ),
        mock.patch("lightning_sdk.datasets._download_dataset_version") as download_version,
    ):
        result = download_dataset(
            "my-org/my-teamspace/my-dataset",
            target_path=str(tmp_path),
            num_workers=3,
            part_size=1024,
            as_zip=as_zip,
            unzip=unzip,
        )

    expected_path = str(tmp_path / expected_name)
    assert result.path == expected_path
    download_version.assert_called_once_with(
        project_id="project-id",
        dataset_name="my-dataset",
        version="v7",
        target_path=expected_path,
        cluster_id=None,
        dataset_id="dataset-id",
        num_workers=3,
        part_size=1024,
        as_zip=as_zip,
        unzip=unzip,
    )


def test_download_dataset_rejects_zip_and_unzip():
    with pytest.raises(ValueError, match="cannot both be True"):
        download_dataset("my-org/my-teamspace/my-dataset", as_zip=True, unzip=True)


def test_download_dataset_version_defaults_to_directory(tmp_path):
    payload = b"raw dataset contents"
    files = [{"filepath": "/nested/data.txt", "url": "https://files/data", "size": len(payload)}]
    output = tmp_path / "dataset_v1"

    with (
        _mock_files_api(files),
        mock.patch("requests.get", side_effect=_range_get({"https://files/data": payload})),
        mock.patch("concurrent.futures.ThreadPoolExecutor", _SyncExecutor),
    ):
        _download_dataset_version(
            project_id="project-id",
            dataset_name="dataset",
            version="v1",
            target_path=str(output),
            dataset_id="dataset-id",
        )

    assert output.is_dir()
    assert (output / "nested" / "data.txt").read_bytes() == payload
    assert not (tmp_path / "dataset_v1.zip").exists()


def test_download_dataset_version_never_auto_extracts(tmp_path):
    payload = _zip_payload({"nested/data.txt": b"still archived"})
    files = [{"filepath": "dataset.zip", "url": "https://files/archive", "size": len(payload)}]
    output = tmp_path / "dataset_v1"

    with (
        _mock_files_api(files),
        mock.patch("requests.get", side_effect=_range_get({"https://files/archive": payload})),
        mock.patch("concurrent.futures.ThreadPoolExecutor", _SyncExecutor),
    ):
        _download_dataset_version(
            project_id="project-id",
            dataset_name="dataset",
            version="v1",
            target_path=str(output),
            dataset_id="dataset-id",
        )

    assert (output / "dataset.zip").read_bytes() == payload
    assert not (output / "nested").exists()


def test_download_dataset_version_opt_in_zip(tmp_path):
    payload = b"archived dataset contents"
    files = [{"filepath": "nested/data.txt", "url": "https://files/data", "size": len(payload)}]
    output = tmp_path / "dataset_v1.zip"

    with (
        _mock_files_api(files),
        mock.patch("requests.get", side_effect=_range_get({"https://files/data": payload})),
        mock.patch("concurrent.futures.ThreadPoolExecutor", _SyncExecutor),
    ):
        _download_dataset_version(
            project_id="project-id",
            dataset_name="dataset",
            version="v1",
            target_path=str(output),
            dataset_id="dataset-id",
            as_zip=True,
        )

    with zipfile.ZipFile(output) as archive:
        assert archive.read("nested/data.txt") == payload


def test_download_dataset_version_explicit_unzip(tmp_path):
    payload = _zip_payload({"nested/data.txt": b"extracted contents"})
    files = [{"filepath": "dataset.zip", "url": "https://files/archive", "size": len(payload)}]
    output = tmp_path / "dataset_v1"
    staging = tmp_path / "staging"

    with (
        _mock_files_api(files),
        mock.patch("requests.get", side_effect=_range_get({"https://files/archive": payload})),
        mock.patch("concurrent.futures.ThreadPoolExecutor", _SyncExecutor),
        mock.patch(
            "lightning_sdk.lightning_cloud.utils.dataset.tempfile.mkdtemp",
            return_value=str(staging),
        ),
    ):
        _download_dataset_version(
            project_id="project-id",
            dataset_name="dataset",
            version="v1",
            target_path=str(output),
            dataset_id="dataset-id",
            unzip=True,
        )

    assert (output / "nested" / "data.txt").read_bytes() == b"extracted contents"
    assert not (output / "dataset.zip").exists()
    assert not staging.exists()


@pytest.mark.parametrize(
    "files",
    [
        [{"filepath": "data.txt", "url": "https://files/data", "size": 1}],
        [
            {"filepath": "one.zip", "url": "https://files/one", "size": 1},
            {"filepath": "two.zip", "url": "https://files/two", "size": 1},
        ],
    ],
)
def test_download_dataset_version_unzip_requires_one_zip(tmp_path, files):
    with (
        _mock_files_api(files),
        mock.patch("requests.get") as get,
        pytest.raises(ValueError, match="exactly one .zip artifact"),
    ):
        _download_dataset_version(
            project_id="project-id",
            dataset_name="dataset",
            version="v1",
            target_path=str(tmp_path / "output"),
            dataset_id="dataset-id",
            unzip=True,
        )

    get.assert_not_called()


def test_download_dataset_files_skips_missing_url(tmp_path):
    files = [{"filepath": "missing.bin", "size": 4}]
    with mock.patch("requests.get") as get:
        _download_dataset_files(
            files,
            str(tmp_path),
            "project-id",
            refresh_file=lambda _: {"url": None, "size": 0},
        )

    get.assert_not_called()
    assert not (tmp_path / "missing.bin").exists()


@pytest.mark.parametrize("filepath", ["../escape.txt", "/../escape.txt", "C:\\temp\\escape.txt"])
def test_download_dataset_files_rejects_unsafe_remote_paths(tmp_path, filepath):
    files = [{"filepath": filepath, "url": "https://files/data", "size": 4}]
    with (
        mock.patch("requests.get") as get,
        pytest.raises(ValueError, match="Unsafe dataset filepath"),
    ):
        _download_dataset_files(
            files,
            str(tmp_path / "output"),
            "project-id",
            refresh_file=lambda _: {"url": None, "size": 0},
        )

    get.assert_not_called()


def test_download_dataset_version_rejects_zip_member_traversal(tmp_path):
    payload = _zip_payload({"../escape.txt": b"escaped"})
    files = [{"filepath": "dataset.zip", "url": "https://files/archive", "size": len(payload)}]
    output = tmp_path / "output"
    staging = tmp_path / "staging"

    with (
        _mock_files_api(files),
        mock.patch("requests.get", side_effect=_range_get({"https://files/archive": payload})),
        mock.patch("concurrent.futures.ThreadPoolExecutor", _SyncExecutor),
        mock.patch(
            "lightning_sdk.lightning_cloud.utils.dataset.tempfile.mkdtemp",
            return_value=str(staging),
        ),
        pytest.raises(ValueError, match="Unsafe ZIP member path"),
    ):
        _download_dataset_version(
            project_id="project-id",
            dataset_name="dataset",
            version="v1",
            target_path=str(output),
            dataset_id="dataset-id",
            unzip=True,
        )

    assert not (tmp_path / "escape.txt").exists()
    assert not output.exists()
    assert not staging.exists()
