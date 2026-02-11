import io
import shutil
import tempfile
from numbers import Real
from pathlib import Path
from time import perf_counter

import streamlit as st
import requests
from dxtbx.model.experiment_list import ExperimentListFactory

from dials2imgcif import guess_archive_type, guess_file_type, make_cif, ArchiveUrl
from cache_dir import DownloadsCache

DATA_DIR = Path("/gpfs/exfel/data/scratch/kluyvert/imgcif-source-data")
ARCHIVE_EXTS = {'ZIP': '.zip', 'TGZ': '.tar.gz', 'TBZ': '.tar.bz2', 'TXZ': '.tar.xz'}
SIZE_LIMIT = 5 * (1024 ** 3)

download_cache = DownloadsCache(DATA_DIR)

def fmt_bytes(n: Real) -> str:
    n = float(n)
    for suffix in ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']:
        if n < 1024:
            break
        n /= 1024

    return f'{n:.1f} {suffix}'


def download_and_unpack(archive_url, ext):
    dir_for_url = download_cache.path_for(archive_url)
    if dir_for_url.is_dir():
        contents = list(dir_for_url.iterdir())
        print("Found something", contents)
        if contents:
            return dir_for_url

    resp = requests.get(archive_url, stream=True)
    if (size := int(resp.headers.get('content-length', '0'))) > SIZE_LIMIT:
        raise RuntimeError(f"Download too large ({fmt_bytes(size)})")

    with tempfile.NamedTemporaryFile(suffix=ext) as tf:
        download_progress = st.progress(0, f'Downloading {fmt_bytes(size)}')
        bytes_read = 0
        t0 = perf_counter()
        for chunk in resp.iter_content(chunk_size=4 * 1024 * 1024):
            bytes_read += len(chunk)
            if bytes_read > size:
                raise RuntimeError("Server lied about download size")
            tf.write(chunk)
            rate = bytes_read / (perf_counter() - t0)
            msg = f'Downloaded {fmt_bytes(bytes_read)} / {fmt_bytes(size)} ({fmt_bytes(rate)}/s)'
            download_progress.progress(bytes_read / size, msg)
        download_progress.empty()

        with download_cache.tmpdir() as unpacked:
            print("Unpacking to", unpacked)
            with st.spinner("Unpacking"):
                shutil.unpack_archive(tf.name, unpacked)
            print("Renaming to", dir_for_url)
            unpacked.rename(dir_for_url)

        return dir_for_url


print("Running script")

st.title("ImgCIF creator")

url = st.text_input("Download URL")

archive_fmt_guess = guess_archive_type(url)
archive_type = st.pills(
    "File format", ["ZIP", "TGZ", "TBZ", "TXZ"], default=archive_fmt_guess
)

if not url or not archive_type:
    st.stop()

unpacked_archive = download_and_unpack(url, ARCHIVE_EXTS[archive_type])
st.text(unpacked_archive)

path_in_archive = st.text_input("Data path in archive")
if not path_in_archive:
    st.stop()

#expt_path = st.text_input("EXPT file", None)
#if expt_path is None:
#    st.stop()

@st.cache_data(show_spinner="Reading files...")
def load_expt_list(path):
    return ExperimentListFactory.from_filenames([path])

expts = load_expt_list(unpacked_archive / path_in_archive)

st.write(f"Found {len(expts)} experiment(s) with "
         f"{sum(len(e.imageset) for e in expts)} total images.\n")

doi = st.text_input("DOI (optional)", None)

imgset0 = expts[0].imageset
fmt_guess = guess_file_type(imgset0.get_path(0), imgset0.get_format_class())
file_type = st.pills("File format", ["HDF5", "CBF", "TIFF", "SMV"], default=fmt_guess)

if file_type is None:
    st.stop()

st.write(f"File format: {file_type}")

download_info = [
    ArchiveUrl(
        url,
        unpacked_archive,
        archive_type,
    )
]

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
st.download_button("Download CIF file", sio.getvalue(), file_name="generated.cif", on_click="ignore", icon=":material/download:")

st.header("ImgCIF preview")
st.text("Showing a subset of the data")
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
