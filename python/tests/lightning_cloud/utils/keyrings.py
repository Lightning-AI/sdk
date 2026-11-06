import json
import os
import pathlib
import tempfile
import time

from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

KEYRING_PATH = "LIGHTNING_TEST_KEYRING"


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.entries = {}

    def get_password(self, service, username):
        return self.entries.get((service, username))

    def set_password(self, service, username, password):
        self.entries[(service, username)] = password

    def delete_password(self, service, username):
        if self.entries.pop((service, username), None) is None:
            raise PasswordDeleteError(username)


class FileKeyring(KeyringBackend):
    """A keyring several processes share, in the file named by LIGHTNING_TEST_KEYRING."""

    priority = 1

    def get_password(self, service, username):
        return self._read().get(f"{service} {username}")

    def set_password(self, service, username, password):
        entries = self._read()
        entries[f"{service} {username}"] = password
        self._write(entries)

    def delete_password(self, service, username):
        entries = self._read()
        if entries.pop(f"{service} {username}", None) is None:
            raise PasswordDeleteError(username)
        self._write(entries)

    def _path(self):
        return pathlib.Path(os.environ[KEYRING_PATH])

    def _read(self):
        try:
            return json.loads(self._path().read_text())
        except FileNotFoundError:
            return {}

    def _write(self, entries):
        path = self._path()
        fd, tmp = tempfile.mkstemp(dir=path.parent)
        with os.fdopen(fd, "w") as file:
            json.dump(entries, file)
        for _ in range(100):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                # Windows refuses to replace a file another process has open.
                time.sleep(0.01)
        os.replace(tmp, path)
