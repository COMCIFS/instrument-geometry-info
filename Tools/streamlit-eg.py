import io

import streamlit as st
import numpy as np
from dxtbx.model.experiment_list import ExperimentListFactory

from dials2imgcif import guess_file_type, make_cif, ArchiveUrl

print("Running script")

st.title("ImgCIF creator")

expt_path = st.text_input("EXPT file", None)
if expt_path is None:
    st.stop()

expts = ExperimentListFactory.from_json_file(expt_path)

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
        "https://data.proteindiffraction.org/other/6r17.tar.bz2", 
        "/gpfs/exfel/data/scratch/dallanto/DATA/MCBF/DLS-I24/proteindiffraction.org-6r17-syce2tex12-cbf-partial/",
        "TBZ"
    )
]

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
