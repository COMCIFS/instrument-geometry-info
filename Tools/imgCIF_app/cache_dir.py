import errno
import hashlib
import json
import os
import os.path as osp
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from secrets import token_hex

INFO_FILE = ".cache-info"

class DownloadsCache:
    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash(url):
        return hashlib.sha3_256(url.encode('utf-8')).hexdigest()

    def path_for(self, url):
        return self.folder / self._hash(url)

    def prepare(self, url):
        p = self.path_for(url)
        p.mkdir(exist_ok=True)
        return p

    def get_info(self, url):
        return json.loads((self.path_for(url) / INFO_FILE).read_text())

    def set_info(self, url, download_size=None):
        d = {"url": url, "download_size": download_size}
        (self.path_for(url) / INFO_FILE).write_text(json.dumps(d))

    def get(self, url):
        if (subdir := self.path_for(url)).is_dir():
            (subdir / INFO_FILE).touch()  # Update mtime
            return subdir
        return None  # Not in cache

    @contextmanager
    def tmpdir(self):
        td = tempfile.mkdtemp(dir=self.folder, prefix=".creating-")
        try:
            yield Path(td)
        except:
            shutil.rmtree(td)
            raise

    def delete(self, dir_path: os.PathLike):
        # We don't want to use a directory while deleting it, so rename it
        # first to take it out of use, and then clean it up.
        for _ in range(100):
            renamed = self.folder / f".deleting-{token_hex(16)}"
            try:
                os.rename(dir_path, renamed)
                break
            except OSError as e:
                if e.errno != errno.ENOTEMPTY:
                    raise
        else:
            raise RuntimeError("Unable to rename directory for deletion")

        shutil.rmtree(renamed)

    @staticmethod
    def _entry_last_used(p: os.PathLike):
        try:
            return (Path(p) / INFO_FILE).stat().st_mtime
        except FileNotFoundError:
            return 0  # Delete folders missing the marker first

    @staticmethod
    def _entry_size(p: os.PathLike):
        s = 0
        for root, dir, files in os.walk(p):
            s += sum(osp.getsize(osp.join(root, f)) for f in files)
        return s

    def _entries(self):
        with os.scandir(self.folder) as it:
            for de in it:
                if de.is_dir() and not de.name.startswith("."):
                    yield de

    def release_space(self, max_bytes_keep: int):
        entries = sorted(self._entries(), key=self._entry_last_used, reverse=True)
        # Find how many entries to keep
        bytes_found = 0
        for i, de in enumerate(entries):
            bytes_found += self._entry_size(de)
            if bytes_found > max_bytes_keep:
                break
        else:
            return

        for de in entries[i:]:  # Remove oldest entries
            self.remove(de)
