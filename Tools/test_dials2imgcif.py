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
        d['vector'] = np.array((
            float(cifd[f'_axis.vector[{d}]'][i]) for d in (1, 2, 3)
        ))
        d['offset'] = np.array((
            float(cifd[f'_axis.offset[{d}]'][i]) for d in (1, 2, 3)
        ))

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
