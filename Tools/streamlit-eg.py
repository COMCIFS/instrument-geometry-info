import io
import posixpath
import shutil
import tempfile
from numbers import Real
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

import streamlit as st
import requests
from dxtbx.model.experiment_list import ExperimentListFactory

from imgCIF_app.core import (
    guess_archive_type, guess_file_type, make_cif, ArchiveUrl, DirectoryUrl
)
from imgCIF_app.tui import extrapolate_sequence
from imgCIF_app.cache_dir import DownloadsCache

DATA_DIR = Path("/gpfs/exfel/data/scratch/kluyvert/imgcif-source-data")
ARCHIVE_EXTS = {'ZIP': '.zip', 'TGZ': '.tar.gz', 'TBZ': '.tar.bz2', 'TXZ': '.tar.xz'}
SIZE_LIMIT = 5 * (1024 ** 3)

download_cache = DownloadsCache(DATA_DIR / "downloads")

def fmt_bytes(n: Real) -> str:
    n = float(n)
    for suffix in ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']:
        if n < 1024:
            break
        n /= 1024

    return f'{n:.1f} {suffix}'

def _download(url, fout):
    resp = requests.get(url, stream=True)
    if (size := int(resp.headers.get('content-length', '0'))) > SIZE_LIMIT:
        raise RuntimeError(f"Download too large ({fmt_bytes(size)})")

    download_progress = st.progress(0, f'Downloading {fmt_bytes(size)}')
    bytes_read = 0
    t0 = perf_counter()
    for chunk in resp.iter_content(chunk_size=4 * 1024 * 1024):
        bytes_read += len(chunk)
        if bytes_read > size:
            raise RuntimeError("Server lied about download size")
        fout.write(chunk)
        rate = bytes_read / (perf_counter() - t0)
        msg = f'Downloaded {fmt_bytes(bytes_read)} / {fmt_bytes(size)} ({fmt_bytes(rate)}/s)'
        download_progress.progress(bytes_read / size, msg)
    download_progress.empty()


def download_multi(urls_paths, expected_size: int, chunk_size=(4 * 1024 * 1024)):
    download_progress = st.progress(0, f'Downloading {fmt_bytes(expected_size)}')
    bytes_read = 0
    t0 = perf_counter()
    file_sizes = []
    for url, p in urls_paths:
        if p.is_file():
            file_size = p.stat().st_size
            bytes_read += file_size
            file_sizes.append(file_size)
            continue

        resp = requests.get(url, stream=True)
        resp.raise_for_status()

        fd, tmp_path = tempfile.mkstemp(dir=p.parent, suffix=p.suffix)
        try:
            with open(fd, 'wb') as f:
                file_size = 0
                for chunk in resp.iter_content(chunk_size):
                    file_size += len(chunk)
                    bytes_read += len(chunk)
                    if bytes_read > SIZE_LIMIT:
                        raise RuntimeError(f"Download size exceeded limit ({fmt_bytes(SIZE_LIMIT)}")
                    f.write(chunk)
                    rate = bytes_read / (perf_counter() - t0)
                    msg = f'Downloaded {fmt_bytes(bytes_read)} / {fmt_bytes(expected_size)} ({fmt_bytes(rate)}/s)'
                    download_progress.progress(bytes_read / expected_size, msg)
                file_sizes.append(file_size)
            Path(tmp_path).rename(p)
        except:
            Path(tmp_path).unlink()
            raise
    download_progress.empty()

    return file_sizes


def download_and_unpack(archive_url, ext):
    dir_for_url = download_cache.path_for(archive_url)
    if dir_for_url.is_dir():
        contents = list(dir_for_url.iterdir())
        print("Found something", contents)
        if contents:
            return dir_for_url

    with tempfile.NamedTemporaryFile(suffix=ext) as tf:
        _download(archive_url, tf)

        with download_cache.tmpdir() as unpacked:
            print("Unpacking to", unpacked)
            with st.spinner("Unpacking"):
                shutil.unpack_archive(tf.name, unpacked)
            print("Renaming to", dir_for_url)
            unpacked.rename(dir_for_url)

        return dir_for_url


def download_archives(urls, ext, expected_size):
    urls_to_download = []
    for url in urls:
        if download_cache.get(url) is None:
            urls_to_download.append(url)

    with tempfile.TemporaryDirectory(prefix="download-") as td:
        td = Path(td)
        urls_paths = [(url, td / f"{i:04}{ext}") for i, url in enumerate(urls_to_download)]
        sizes = download_multi(urls_paths, expected_size)

        with st.spinner("Unpacking"):
            for (url, arc_path), sz in zip(urls_paths, sizes):
                with download_cache.tmpdir() as unpacked:
                    # TODO: make this more defensive against odd archives
                    shutil.unpack_archive(arc_path, unpacked)
                unpacked.rename(download_cache.path_for(url))
                download_cache.set_info(url, download_size=sz)

    return [download_cache.path_for(u) for u in urls]


def base_url_and_rel_paths(urls):
    s0 = urlsplit(urls[0])
    fixed = (s0.scheme, s0.netloc, s0.query)
    paths = [s0.path]
    for u in urls[1:]:
        s = urlsplit(u)
        if (s.scheme, s.netloc, s.query) != fixed:
            raise ValueError("Only the path of URLs may vary")
        paths.append(s.path)
    common_path = posixpath.commonpath(paths)
    common_url = urlunsplit((s0.scheme, s0.netloc, common_path, s0.query, ''))
    return common_url, [posixpath.relpath(p, common_path) for p in paths]


def download_files(urls, expected_size):
    common_url, rel_paths = base_url_and_rel_paths(urls)
    dir_for_url = download_cache.prepare(common_url)

    urls_paths = [(u, dir_for_url / rp) for (u, rp) in zip(urls, rel_paths)]
    download_multi(urls_paths, expected_size)

    return common_url, dir_for_url, rel_paths


def total_download_size(urls):
    total_size = 0
    for url in urls:
        r = requests.head(url)
        r.raise_for_status()
        total_size += int(r.headers.get('content-length', '0'))
    return total_size


print("Running script")

st.title("ImgCIF creator")

n_downloads = st.number_input("Number of downloads", min_value=1)

url1 = st.text_input("Download URL" + (" 1" if n_downloads > 1 else ""))
urls = [url1]
if n_downloads > 1:
    url2 = st.text_input("Download URL 2")

    urls.append(url2)
    if n_downloads > 2:
        if url1 and url2:
            urls.extend(extrapolate_sequence(url1, url2, n_downloads))
            st.text(f"Extrapolated URLs up to {urls[-1]}")
        else:
            st.text("Additional URLs will be extrapolated as a sequence")
            st.stop()
elif not url1:
    st.stop()

if (total_size := total_download_size(urls)) > SIZE_LIMIT:
    st.warning(f"Download size {fmt_bytes(total_size)} exceeds limit of "
               f"{fmt_bytes(SIZE_LIMIT)}. Please use a local tool to create "
               f"ImgCIF metadata.")
    st.stop()

archive_type_guess = guess_archive_type(url1)

is_archive = st.toggle("Unpack archives (zip / tar)",
                       value=(archive_type_guess is not None))

download_info = []

if is_archive:
    archive_type = st.pills(
        "Archive format", ["ZIP", "TGZ", "TBZ", "TXZ"], default=archive_type_guess
    )
    archive_ext = ARCHIVE_EXTS[archive_type]

    unpacked_dirs = download_archives(urls, archive_ext, total_size)
    download_info = [
        ArchiveUrl(u, p, archive_type) for (u, p) in zip(urls, unpacked_dirs)
    ]

    path_in_archive = st.text_input(
        "Data path in archive",
        help="Path to a file or a folder inside the archive, or a pattern like `*.cbf`")
    if not path_in_archive:
        st.stop()

    paths = []
    for au in download_info:
        paths.extend(au.dir.glob(path_in_archive))
else:
    common_url, download_dir, rel_paths = download_files(urls, total_size)
    download_info.append(
        DirectoryUrl(common_url, download_dir)
    )
    paths = [download_dir / p for p in rel_paths]

#expt_path = st.text_input("EXPT file", None)
#if expt_path is None:
#    st.stop()

@st.cache_data(show_spinner="Reading files...")
def load_expt_list(paths: tuple):
    return ExperimentListFactory.from_filenames(paths)

expts = load_expt_list(tuple(paths))

st.write(f"Found {len(expts)} experiment(s) with "
         f"{sum(len(e.imageset) for e in expts)} total images.\n")

doi = st.text_input("DOI (optional)", None)

imgset0 = expts[0].imageset
fmt_guess = guess_file_type(imgset0.get_path(0), imgset0.get_format_class())
file_type = st.pills("File format", ["HDF5", "CBF", "TIFF", "SMV"], default=fmt_guess)

if file_type is None:
    st.stop()

st.write(f"File format: {file_type}")

st.divider()

sio = io.StringIO()
make_cif(
    expts,
    sio,
    data_name="generated",
    locations=download_info,
    doi=doi,
    file_type=file_type,
    overload_value=None,
)
st.header("ImgCIF output")
st.download_button(
    "Download CIF file",
    sio.getvalue(),
    file_name="generated.cif",
    on_click="ignore",
    icon=":material/download:",
    type="primary"
)

st.text("Preview: showing a subset of the data")
sio = io.StringIO()
sio.write("# ImgCIF preview - incomplete data\n\n")
make_cif(
    expts,
    sio,
    data_name="preview",
    locations=download_info,
    doi=doi,
    file_type=file_type,
    overload_value=None,
    frame_limit=5,
)

st.code(sio.getvalue(), language=None)
