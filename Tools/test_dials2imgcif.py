from pathlib import Path

import numpy as np
from CifFile import ReadCif

from dials2imgcif import main

samples_dir = Path(__file__).parent / 'samples'

def get_axes(cifd) -> dict:
    fields = ['id', 'depends_on', 'equipment', 'type']
     #   'vector[1]', 'vector[2]', 'vector[3]',
     #   'rotation[1]', 'rotation[2]', 'rotation[3]',
    axes = {}
    for i, name in enumerate(cifd['_axis.id']):
        axes[name] = d = {f: cifd[f'_axis.{f}'][i] for f in fields}
        d['vector'] = np.array([
            float(cifd[f'_axis.vector[{d}]'][i]) for d in (1, 2, 3)
        ])
        d['offset'] = np.array([
            float(cifd[f'_axis.offset[{d}]'][i]) for d in (1, 2, 3)
        ])

    return axes


def test_basic(tmp_path):
    out_path = tmp_path / 'result.cif'
    main([
        str(samples_dir / '6RLR-cbf.expt'),
        "--no-check-format",
        "--dir", "/gpfs/exfel/data/scratch/kluyvert/imgcif-conv/6RLR/cbf/",
        "--url", "https://zenodo.org/records/5886687/files/cbf_b4_1.tar.bz2",
        "-o", str(out_path)
    ])
    assert out_path.is_file()

    res = ReadCif(str(out_path))['result']
    np.testing.assert_allclose(
        float(res['_diffrn_radiation_wavelength.value']), 0.97949
    )
    axes = get_axes(res)

    gonio_ax_names = {k for (k, v) in axes.items() if v['equipment'] == 'goniometer'}
    assert gonio_ax_names == {'GON_PHI', 'GON_CHI', 'GON_OMEGA'}
    assert axes['GON_OMEGA']['depends_on'] == '.'

    np.testing.assert_allclose(
        np.array([float(n) for n in res['_diffrn_scan_frame.integration_time']]), .01
    )

    assert res['_array_data_external_data.format'][0] == 'CBF'
    assert res['_array_data_external_data.uri'][0] == 'https://zenodo.org/records/5886687/files/cbf_b4_1.tar.bz2'
    assert res['_array_data_external_data.archive_format'][0] == 'TBZ'
    assert res['_array_data_external_data.archive_path'][0] == 's01f0001.cbf'


def test_rsync_url(tmp_path):
    out_path = tmp_path / 'result.cif'
    main([
        str(samples_dir / '8CUB.expt'),
        "--no-check-format",
        "--dir", "/gpfs/exfel/data/scratch/kluyvert/imgcif-conv/8CUB/973/",
        "--url-base", "rsync://data.sbgrid.org/10.15785/SBGRID/973",
        "-o", str(out_path)
    ])
    assert out_path.is_file()

    res = ReadCif(str(out_path))['result']
    assert res['_array_data_external_data.uri'] == [
        f"rsync://data.sbgrid.org/10.15785/SBGRID/973/PNP545_{i:04}.img"
        for i in range(1, 91)
    ]


def test_from_hdf5(tmp_path):
    out_path = tmp_path / 'result.cif'
    main([
        str(samples_dir / 'P5P1' / 'FJ_P5P1'/ 'FJ_P5P1_1_master.h5'),
        "--dir", str(samples_dir / 'P5P1'),
        "--url", "https://zenodo.org/records/10972988/files/FJ_P5P1.zip",
        "-o", str(out_path)
    ])
    assert out_path.is_file()

    res = ReadCif(str(out_path))['result']
    assert res['_array_data_external_data.uri'][0] == (
        "https://zenodo.org/records/10972988/files/FJ_P5P1.zip"
    )
    assert res['_array_data_external_data.archive_path'] == (
        ["FJ_P5P1/FJ_P5P1_1_000001.h5"] * 1000 +
        ["FJ_P5P1/FJ_P5P1_1_000002.h5"] * 1000 +
        ["FJ_P5P1/FJ_P5P1_1_000003.h5"] * 1000 +
        ["FJ_P5P1/FJ_P5P1_1_000004.h5"] * 600
    )
    assert res['_array_data_external_data.path'] == ["/data"] * 3600


def test_axis_rotation(tmp_path):
    out_path = tmp_path / 'result.cif'
    main([
        str(samples_dir / '6R17.expt'),
        "--no-check-format",
        "--dir", "/gpfs/exfel/data/scratch/dallanto/DATA/MCBF/DLS-I24/proteindiffraction.org-6r17-syce2tex12-cbf-partial/",
        "--url", "https://data.proteindiffraction.org/other/6r17.tar.bz2",
        "-o", str(out_path)
    ])
    assert out_path.is_file()

    res = ReadCif(str(out_path))['result']
    axes = get_axes(res)

    gonio_ax_names = {k for (k, v) in axes.items() if v['equipment'] == 'goniometer'}
    assert gonio_ax_names == {'GON_OMEGA'}
    assert axes['GON_OMEGA']['depends_on'] == '.'
    # In the DIALS .expt file, the goniometer axis is y: (0, 1, 0)
    # In ImgCIF that should be converted to x.
    np.testing.assert_allclose(axes['GON_OMEGA']['vector'], [1, 0, 0])

    # The other axes should all have the same rotation applied
    np.testing.assert_allclose(axes['Trans']['vector'], [0, 0, -1])
    np.testing.assert_allclose(axes['ele1_slow']['vector'], [-1, 0, 0])
    np.testing.assert_allclose(axes['ele1_fast']['vector'], [0, -1, 0])


def test_multiframe_tiff(tmp_path):
    out_path = tmp_path / 'result.cif'
    main([
        str(samples_dir / 'xrd-285.expt'),
        "--no-check-format",
        "--dir", "/gpfs/exfel/data/scratch/kluyvert/imgcif-conv/xrd-285/",
        "--url-base", "https://xrda.pdbj.org/rest/public/entries/download/285/",
        "-o", str(out_path)
    ])
    assert out_path.is_file()

    res = ReadCif(str(out_path))['result']

    assert res['_array_data_external_data.uri'][0] == (
        "https://xrda.pdbj.org/rest/public/entries/download/285/frames/2024-10-04_12.32.11_24_0.0419_MicroED_36.tif"
    )
    assert res['_array_data_external_data.frame'] == [str(n+1) for n in range(146)]
    assert '_array_data_external_data.path' not in res
