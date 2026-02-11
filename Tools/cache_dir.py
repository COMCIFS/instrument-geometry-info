import hashlib
import os
import os.path as osp
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

class DownloadsCache:
    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash(url):
        return hashlib.sha3_256(url.encode('utf-8')).hexdigest()

    def path_for(self, url):
        return self.folder / self._hash(url)

    def get(self, url):
        if (subdir := self.path_for(url)).is_dir():
            (subdir / ".cache-for").touch()  # Update mtime
            return subdir
        return None  # Not in cache

    @contextmanager
    def tmpdir(self):
        td = tempfile.mkdtemp(dir=self.folder, prefix="creating-")
        try:
            yield Path(td)
        except:
            shutil.rmtree(td)
            raise

    @contextmanager
    def new_entry(self, url):
        hashed_url = hashlib.sha3_256(url.encode('utf-8')).hexdigest()
        final_dir = self.folder / hashed_url
        tmpdir = Path(tempfile.mkdtemp(dir=self.folder, prefix="creating-"))
        try:
            (tmpdir / ".cache-for").write_text(url)
            yield tmpdir, final_dir
        except:
            shutil.rmtree(tmpdir)
            raise
        else:
            tmpdir.rename(final_dir)


    @staticmethod
    def _entry_last_used(p: os.PathLike):
        try:
            return (Path(p) / ".cache-for").stat().st_mtime
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
                if de.is_dir() and not de.name.startswith("creating-"):
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
            shutil.rmtree(de)
