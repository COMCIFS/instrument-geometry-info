"""
Ported from 
https://github.com/COMCIFS/instrument-geometry-info/blob/main/Tools/dials_expt_to_imgcif.jl
Orignal author: Dr. James Hester, ANSTO, Lucas Heights, Australia 
"""

import math
import re
import sys
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from dxtbx.format.FormatSMV import FormatSMV
from dxtbx.model import Detector, ExperimentList, MultiAxisGoniometer, Panel
from dxtbx.model.experiment_list import ExperimentListFactory
from scipy.spatial.transform import Rotation as R

CIF_HEADER = """\
#\\#CIF_2.0
# CIF converted from DIALS .expt file
# Conversion routine version 0.1
data_{name}
"""

GONIO_DEFAULT_AXIS = 'Omega'  # Used when goniometer has 1 nameless axis

#=== Utilities ===
# will go into an external library source-file later

def debug(label, object):
    """Simple object content exposure as debug info
    """
    print(f'DEBUG - {label}: {object}')

#=== Geometry ===

def get_axes_info(expts: ExperimentList):
    gon_axes = get_gon_axes(expts)

    primary_gonio_axes = [v for v in gon_axes.values() if v['next'] == '.']
    if len(primary_gonio_axes) != 1:
        raise AssertionError(f"{len(primary_gonio_axes)} != 1 primary goniometer axes")
    primary_axis = primary_gonio_axes[0]['axis']
    if abs(primary_axis[2]) > 0.0001:
        raise ValueError("Primary axis had an unexpected z component")

    if np.allclose(primary_axis, [1., 0., 0.]):
        axis_rotation = R.identity()
    else:
        axis_rotation, *_ = R.align_vectors([1., 0., 0.], primary_axis)
        print("Rotating axis vectors with matrix:")
        print(axis_rotation.as_matrix())
        rotvec = axis_rotation.as_rotvec(degrees=True)
        rot_angle = np.linalg.norm(rotvec)
        print(f"Equivalent to {rot_angle:.3f} degrees rotation around {rotvec / rot_angle}")
        np.testing.assert_allclose(
            axis_rotation.apply(primary_axis), [1., 0., 0.], atol=1e-8
        )

    gon_axes = {k: v | {'axis': axis_rotation.apply(v['axis'])}
                for k, v in gon_axes.items()}

    det_axes = get_det_axes(expts, axis_rotation)
    srf_axes = get_srf_axes(expts, axis_rotation)
    
    return gon_axes, det_axes, srf_axes


def get_gon_axes(expts: ExperimentList):
    """A goniometer in DIALS is a set of fixed axes, one of which rotates.
       If an axis changes direction, that is a new goniometer.
    """

    gon0 = expts[0].goniometer


    axis_dict = {}

    if isinstance(gon0, MultiAxisGoniometer):
        names = list(gon0.get_names())

        # Sanity check
        for i, e in enumerate(expts[1:]):
            assert isinstance(e.goniometer, MultiAxisGoniometer), "Goniometer type varies"
            _names = list(e.goniometer.get_names())
            assert _names == names, f"{_names} != {names} (expt {i})"

        n_axes = len(names)
        for i in range(n_axes):
            axis_dict[names[i]] = {
                'axis': gon0.get_axes()[i],
                'vals': [e.goniometer.get_angles()[i] for e in expts],
                'next': '.' if i == (n_axes - 1) else f'{names[i + 1]}'
            }
    else:  # single axis then
        #assert(len(g_info) == 1)
        axis_dict[GONIO_DEFAULT_AXIS] = {
            'axis': gon0.get_rotation_axis(),  #g_dict['rotation_axis'],
            'next': '.',
        }

    debug('axes in processed dict', axis_dict)
    return axis_dict


def get_det_axes(expts: ExperimentList, axis_rotation):
    """Determine the axes that move the detector.
       For axes describing pixel positions, see <def surface_axes>.

       A detector is distinct if its position changes in any way.
       So a change in distance or 2 theta is a "new" detector.
       A DIALS detector includes a list of panels arranged in a hierarchy.
       The two-theta angle is absorbed into the panel centre position.

       We think a detector is the same if there are the same number of panels,
       with the same names.

       For two theta and distance, we find the corresponding (virtual) panel
       that is orthonormal to the beam
    """

    d_info = expts[0].detector

    # Sanity check 
    pp = find_perp_panel(d_info, axis_rotation)
    if pp is None:
        raise AssertionError('Unable to find a panel perpendicular to the beam at tth = 0')

    axis_dict = {}

    # two theta for each detector position
    axis_info = [get_two_theta(e.detector, axis_rotation) for e in expts]

    # Only a non-zero tth will give us the axis direction, else no tth required
    poss_axes = [x for x in axis_info if x[1] is not None]
    debug('Possible axes:', poss_axes)

    if len(poss_axes) > 0:
        axis_dict['Two_Theta'] = {
            'axis': poss_axes[0][1],  # strictly != first(...) in Julia
            'vals': [x[0] for x in axis_info],
            'next': '.',
            'type': 'rotation'
        }
    
    dists = [get_distance(e.detector[pp], axis_rotation)
             for e in expts]

    axis_dict['Trans'] = {
        'axis': [0, 0, -1],
        'vals': dists,
        'next': 'Two_Theta' if ('Two_Theta' in axis_dict) else '.',
        'type': 'translation'
    }
    return axis_dict


def get_two_theta(detector: Detector, axis_rotation):
    """ Calculate the rotation required to make the normal to the module
        parallel to the beam. This assumes that the panel provided is
        perpendicular to the beam at tth = 0.
        <detector> is a single entry i.e. list element under key 'detector'.
    """

    pp = find_perp_panel(detector, axis_rotation)

    panel = detector[pp]
    p_orth = np.cross(
        axis_rotation.apply(panel.get_fast_axis()),
        axis_rotation.apply(panel.get_slow_axis())
    )
    p_onrm = p_orth / np.linalg.norm(p_orth)
    #debug('Normal to surface', p_onrm)

    if p_onrm[2] > 0: #pointing towards sample
        p_onrm *= -1.0

    if np.linalg.norm(p_onrm - [0,0,-1]) < 0.0001:
        return 0.0, None

    rot_obj, *_ = R.align_vectors(np.array([0,0,-1]), p_onrm)
    rot_vec = rot_obj.as_rotvec(degrees=True)
    tth_angl = np.linalg.norm(rot_vec)
    tth_axis = rot_vec / tth_angl

    return tth_angl, tth_axis


def get_distance(panel: Panel, axis_rotation):

    # Get projection of a pixel vector onto the normal to the panel

    p_orth = np.cross(
        axis_rotation.apply(panel.get_fast_axis()),
        axis_rotation.apply(panel.get_slow_axis())
    )
    p_onrm = p_orth / np.linalg.norm(p_orth)
    origin = axis_rotation.apply(panel.get_origin())
    return abs(np.dot(origin, p_onrm))


def find_perp_panel(d_info: Detector, axis_rotation):
    """ Find a panel with normal having x component 0
        Returns: the index of the first panel the meets the requirement
    """

    for i, p in enumerate(d_info):
        p_orth = np.cross(
            axis_rotation.apply(p.get_fast_axis()),
            axis_rotation.apply(p.get_slow_axis())
        )
        p_onrm = p_orth / np.linalg.norm(p_orth)

        if math.isclose(p_onrm[0], 0.0, abs_tol=0.0001):
            # can be rotated about X to zero
            return i

    return None


def get_srf_axes(expts: ExperimentList, axis_rotation):
    """ Return the axis directions of each panel when tth = 0
    """
    
    d_info = expts[0].detector
    panel_names = [p.get_name() for p in d_info]

    # Sanity check
    for i, e in enumerate(expts[1:], start=1):
        _panel_names = [p.get_name() for p in e.detector]
        assert _panel_names == panel_names, f"{_panel_names} != {panel_names} (expt {i})"

    axis_dict = {}
    
    tth_angl, tth_axis = get_two_theta(d_info, axis_rotation)
    for i, panel in enumerate(d_info, start=1):
        fast = axis_rotation.apply(panel.get_fast_axis())
        slow = axis_rotation.apply(panel.get_slow_axis())
        origin = axis_rotation.apply(panel.get_origin())
        
        if tth_axis is not None:
            # rotation matrix from 2theta angle-axis (reverse angle)
            rot_vec = tth_angl * tth_axis  # exp. result in separate test, but may need *-1
            rot_mat = R.from_rotvec(rot_vec, degrees=True).as_matrix()
            # apply to (rotated) detector base axes in order to 'unrotate'
            fast = np.around(np.dot(rot_mat, fast), decimals=3)
            slow = np.around(np.dot(rot_mat, slow), decimals=3)
            origin = np.around(np.dot(rot_mat, origin), decimals=3)

        origin = [origin[0], origin[1], 0.0]   # z component is distance
        
        axis_dict[f'ele{i}_fast'] = {
            'axis': fast,
            'next': "Trans",
            'origin': origin,
            'pix_size': panel.get_pixel_size()[0],
            'num_pix': panel.get_image_size()[0],
            'prec': 1,
            'element': i
        }
        axis_dict[f'ele{i}_slow'] = {
            'axis': slow,
            'next': f'ele{i}_fast',
            'origin': [0.0, 0.0, 0.0],
            'pix_size': panel.get_pixel_size()[1],
            'num_pix': panel.get_image_size()[1],
            'prec': 2,
            'element': i
        }

    return axis_dict


# === Scan information === #

"""
    An "experiment" in the .expt file is roughly the equivalent of a
    "scan" in imgCIF, as long as "beam" and "detector" in "experiment"
    remain the same.

    TODO: determine if stated axis directions change with angle.

    `g_axes` and `d_axes` contain information about axis settings
    for each scan, with the order of appearance corresponding to
    the order they appear in `goniometer` or `detector`
"""

# === Derived information to prepare external links ===

@dataclass
class ArchiveUrl:
    url: str
    dir: Path
    archive_type: str | None

    def cif_fields(self, template_path: Path):
        rel_path = template_path.relative_to(self.dir)
        return {'uri': self.url, 'archive_format': self.archive_type,
                'archive_path_template': str(rel_path)}

@dataclass
class DirectoryUrl:
    url_base: str

    def cif_fields(self, template_path: Path):
        return {'uri_template': self.url_base.rstrip('/') + '/' + template_path.name}

class PlaceholderUrl:
    def cif_fields(self, template_path: Path):
        return {'uri_template': '????'}


def gen_external_locations(
        expts: ExperimentList, locations: list[ArchiveUrl | DirectoryUrl],
        file_type=None,
):
    """ Based on command-line arguments and the scan information collected
        at this point, we create per-scan information to be written out as
        external file links later.
        Returns: a list of image file info dictionaries per scan
    """

    n_scans = len(expts)
    if len(locations) == 1:
        locations *= n_scans
    elif len(locations) != n_scans:
        raise ValueError(
            f"Got {len(locations)} download locations; expected 1 or 1 per scan ({n_scans})"
        )

    ext_info = []

    for expt, download_loc in zip(expts, locations):
        template_path = Path(expt.imageset.get_template())  # complete local path as in expt
        fmt = file_type or guess_file_type(
            template_path.name, expt.imageset.get_format_class()
        )

        n_frames = expt.scan.get_num_images()

        if fmt == 'HDF5':
            total_n_frames = 0
            for file_path, obj_path, n in find_hdf5_images(template_path):
                d = {'format': fmt, 'num_frames': n, 'path': obj_path,
                     'single_file': True} \
                    | download_loc.cif_fields(file_path)
                ext_info.append(d)
                total_n_frames += n
                print(f"{n} images in file {file_path}")
            assert total_n_frames == n_frames, f"{total_n_frames} != {n_frames}"
        else:
            single_file = expt.imageset.data().has_single_file_reader()
            d = {'format': fmt, 'num_frames': n_frames, 'single_file': single_file} \
                | download_loc.cif_fields(template_path)
            ext_info.append(d)
            debug('External name dictionary', d)

    return ext_info


def guess_archive_type(url: str):
    if url.endswith(('.tgz', '.tar.gz')):
        return 'TGZ'
    elif url.endswith(('.tbz', '.tar.bz2')):
        return 'TBZ'
    elif url.endswith(('.txz', '.tar.xz')):
        return 'TXZ'
    elif url.endswith('.zip'):
        return 'ZIP'

    print(f"WARNING: could not guess archive type from URL ({url})")
    return '???'
    

def guess_file_type(name: str, dxtbx_fmt_cls):
    if issubclass(dxtbx_fmt_cls, FormatSMV):
        return 'SMV'
    elif name.endswith('.cbf'):
        return 'CBF'
    elif name.endswith(('.h5', '.nxs')):
        return 'HDF5'
    elif name.endswith('.tif'):
        return 'TIFF'
    else:
        print(f"WARNING: Unable to determine type of image file ({name})")
        return '???'


def find_hdf5_images(master_path):
    master = h5py.File(master_path, 'r')
    data_grp = master['/entry/data']
    for name in sorted(data_grp):
        if not re.match(r'data_\d+$', name):
            continue

        link = data_grp.get(name, getlink=True)
        dset = data_grp[name]
        if isinstance(link, h5py.ExternalLink):
            file_path = (master_path.parent / link.filename)
            obj_path = link.path
        else:
            file_path = master_path
            obj_path = dset.name

        yield file_path, obj_path, dset.shape[0]


# ============ Output =============

def write_doi(doi, outf):
    if doi:
        outf.write(f"_database.dataset_doi   {doi!r}\n")

def write_beam_info(expts: ExperimentList, outf):
    wl = expts[0].beam.get_wavelength()
    for e in expts[1:]:
        assert e.beam.get_wavelength() == wl, f"{e.beam.get_wavelength()} != {wl}"

    cif_block = f"""
_diffrn_radiation_wavelength.id    1
_diffrn_radiation_wavelength.value {wl}
_diffrn_radiation.type             xray

"""
    outf.write(cif_block)

def cif_loop(base_name: str, fields: list, rows) -> str:
    """Assemble a loop_ table ready to be written to a CIF file"""
    for i, row in enumerate(rows, start=1):
        if len(row) == 1 and row[0].startswith('#'):
            continue  # Comment row
        if len(row) != len(fields):
            raise ValueError(
                f"Row {i} has unexpected length ({len(row)} != {len(fields)}"
            )
    lines = ["loop_"] + [
        f" {base_name}.{f}" for f in fields
    ] + [""] + [
        "  " + "\t".join([str(v) for v in r]) for r in rows
    ] + ["", ""]
    return "\n".join(lines)

def write_axis_info(g_axes, d_axes, s_axes, outf):
    """ Write CIF syntax for all axes of the experiment, where axes
        are both from the goniometer and the detector
    """



    fields = [
        "id", "depends_on", "equipment", "type",
        "vector[1]", "vector[2]", "vector[3]", "offset[1]", "offset[2]", "offset[3]",
    ]
    rows = []

    for k, v in g_axes.items():
        debug('Output axis now', k)
        ax = np.array(v['axis']).round(8)
        rows.append((k, v['next'], 'goniometer', 'rotation', ax[0], ax[1], ax[2], 0., 0., 0.))

    # !!! Detector distance is currently not written - as well in the Julia reference
    debug('Detector info', d_axes)
    for k, v in d_axes.items():
        debug('Output axis now', k)
        ax = np.array(v['axis']).round(8)
        rows.append((k, v['next'], 'detector', v['type'], ax[0], ax[1], ax[2], 0., 0., 0.))

    for k, v in s_axes.items():
        debug('Output surface axis', k)
        ax = np.array(v['axis']).round(8)
        origin = np.array(v['origin'])
        rows.append((k, v['next'], 'detector', 'translation',
                     ax[0], ax[1], ax[2], origin[0], origin[1], origin[2]))

    outf.write(cif_loop("_axis", fields, rows))


def write_array_info(det_name, n_elms, s_axes, d_axes, outf, overload_value=None):
    """ Output information about the layout of the pixels. We assume two axes,
        with the first one the fast direction, and that there is no dead space
        between pixels.
    """
    outf.write(f"""\
_diffrn_detector.id        {det_name}
_diffrn_detector.diffrn_id DIFFRN

""")

    outf.write(cif_loop(
        "_diffrn_detector_element",
        ["id", "detector_id"],
        [(f'ELEMENT{i}', det_name) for i in range(1, n_elms+1)]
    ))

    outf.write(cif_loop(
        "_diffrn_detector_axis",
        ["detector_id", "axis_id"],
        [("DETECTOR", ax) for ax in d_axes]
    ))

    outf.write(cif_loop(
        "_array_structure_list_axis",
        ["axis_id", "axis_set_id", "displacement", "displacement_increment"],
        [(ax, i, v['pix_size'] / 2, v['pix_size'])
         for i, (ax, v) in enumerate(s_axes.items(), start=1)]
    ))

    outf.write(cif_loop(
        "_array_structure_list",
        ["array_id", "axis_set_id", "direction", "index", "precedence", "dimension"],
        [(1, i, "increasing", v['prec'], v['prec'], v['num_pix'])
         for i, v in enumerate(s_axes.values(), start=1)]
    ))

    if overload_value is not None:
        outf.write(f"_array_intensities.overload    {overload_value}\n\n")



def write_scan_info(expts: ExperimentList, g_axes, d_axes, outf):
    """ Output scan axis information 
    """
    fields = [
        "scan_id", "axis_id", "displacement_start", "displacement_increment",
        "displacement_range", "angle_start", "angle_increment", "angle_range"
    ]
    rows = []
    fmt = lambda v: format(v, '.2f')

    for s_ix, expt in enumerate(expts):

        scan_id = f'SCAN.{s_ix+1}'

        if isinstance(expt.goniometer, MultiAxisGoniometer):
            gonio_names = expt.goniometer.get_names()
            scan_ax = gonio_names[expt.goniometer.get_scan_axis()]
        else:
            scan_ax = GONIO_DEFAULT_AXIS

        start, step = expt.scan.get_oscillation()
        full_range = step * expt.scan.get_num_images() # to end of final step

        for ax, v in g_axes.items():
            if ax == scan_ax:
                rows.append((
                    scan_id, ax, ".", ".", ".", fmt(start), format(step, '.4f'), fmt(full_range)
                ))
            else:
                rows.append((
                    scan_id, ax, ".", ".", ".", fmt(v['vals'][s_ix]), 0., 0.
                ))

        for ax, v in d_axes.items():
            if ax == "Trans":
                rows.append((
                    scan_id, ax, fmt(v['vals'][s_ix]), 0., 0., ".", ".", "."
                ))
            else:
                rows.append((
                    scan_id, ax, ".", ".", ".", fmt(v['vals'][s_ix]), 0., 0.
                ))

    outf.write(cif_loop("_diffrn_scan_axis", fields, rows))

def write_frame_ids(expts: ExperimentList, outf, scan_frame_limit=np.inf):
    rows = []
    counter = 1
    for s_ix, expt in enumerate(expts, start=1):
        n_frames = expt.scan.get_num_images()
        end_cnt = counter + n_frames - 1
        rows.append((f"SCAN.{s_ix}", f"frm{counter}", f"frm{end_cnt}", n_frames))
        counter = end_cnt + 1

    outf.write(cif_loop(
        "_diffrn_scan",
        ["id", "frame_id_start", "frame_id_end", "frames"],
        rows
    ))

    rows = []
    counter = 1
    for s_ix, expt in enumerate(expts, start=1):
        exp_time = expt.scan.get_exposure_times()
        for f_ix in range(min(expt.scan.get_num_images(), scan_frame_limit)):
            rows.append((f"frm{counter}", f"SCAN.{s_ix}", f_ix + 1, exp_time[f_ix]))
            counter += 1
        if (n_cut := expt.scan.get_num_images() - scan_frame_limit) > 0:
            rows.append((f"# - {n_cut} rows cut for preview -",))

    outf.write(cif_loop(
        "_diffrn_scan_frame",
        ["frame_id", "scan_id", "frame_number", "integration_time"],
        rows
    ))


def write_frame_images(expts: ExperimentList, outf, scan_frame_limit=np.inf):
    """ Link frames to binary images
        TODO: Match array and element names
    """
    rows = []
    counter = 1
    for expt in expts:
        for f_ix in range(min(expt.scan.get_num_images(), scan_frame_limit)):
            rows.append((f"frm{counter}", "ELEMENT", "IMAGE", counter))
            counter += 1
        if (n_cut := expt.scan.get_num_images() - scan_frame_limit) > 0:
            rows.append((f"# - {n_cut} rows cut for preview -",))

    outf.write(cif_loop(
        "_diffrn_data_frame",
        ["id", "detector_element_id", "array_id", "binary_id"],
        rows
    ))

    # Now link images with external locations

    rows = [("IMAGE", i, i) for i in range(1, counter)]
    if (n_cut := sum(e.scan.get_num_images() for e in expts) - (counter - 1)) > 0:
        rows.append((f"# - {n_cut} rows cut for preview -",))
    outf.write(cif_loop(
        "_array_data",
        ["array_id", "binary_id", "external_data_id"],
        rows
    ))



def write_external_locations(ext_info, outf, scan_frame_limit=np.inf):
    """ External locations must be of uniform type, and organised in scan order.
    """
    fields = ['id', 'format', 'uri']
    if 'archive_format' in ext_info[0]:
        fields += ['archive_format', 'archive_path']
    if ext_info[0]['format'] == 'HDF5':
        fields += ['path']
    if ext_info[0]['single_file']:
        fields += ['frame']

    counter = 1
    rows = []
    for extf in ext_info:
        n_frames = min(extf['num_frames'], scan_frame_limit)
        for fr_ix in range(1, n_frames + 1):
            r = [counter, extf['format']]
            if 'uri_template' in extf:
                r += [encode_scan_step(extf['uri_template'], fr_ix)]
            else:
                r += [extf['uri']]

            if 'archive_format' in extf:
                r += [extf['archive_format'],
                      encode_scan_step(extf['archive_path_template'], fr_ix)]

            if extf['format'] == 'HDF5':
                r += [extf['path']]
            if extf['single_file']:
                r += [fr_ix]
            rows.append(r)
            counter += 1
        if (n_cut := extf['num_frames'] - scan_frame_limit) > 0:
            rows.append((f"# - {n_cut} rows cut for preview -",))

    outf.write(cif_loop("_array_data_external_data", fields, rows))


def encode_scan_step(template, val):
    """ Encode the file number into a scan template. The template has a sequence
        of `#` characters for encoding the integer value of the step number.
        The resolved number will be a zero-filled integer as part of the file name.
        For instance: 01_#####.cbf --> 01_00123.cbf for frame 123
    """
    def repl(match):
        width = len(match[1])
        return f"{val:0{width}}."
    return re.sub(r"(#+)\.", repl, template)


def make_cif(expts, outf, data_name, locations, doi=None,
             file_type=None, overload_value=None, frame_limit=np.inf):
    outf.write(CIF_HEADER.format(name=data_name))

    write_doi(doi, outf)

    write_beam_info(expts, outf)

    g_ax, d_ax, s_ax = get_axes_info(expts)
    write_axis_info(g_ax, d_ax, s_ax, outf)

    write_array_info('DETECTOR',
                     len(list(expts[0].detector.iter_panels())),
                     s_ax, d_ax, outf, overload_value)

    write_scan_info(expts, g_ax, d_ax, outf)
    write_frame_ids(expts, outf, frame_limit)
    write_frame_images(expts, outf, frame_limit)

    ext_info = gen_external_locations(
        expts, locations, file_type
    )
    write_external_locations(ext_info, outf, frame_limit)

# ============= main ==============

def parse_commandline(argv):

    ap = ArgumentParser(prog="dials2imgcif")
    ap.add_argument(
        "input_fn",
        type=Path,
        nargs='+',
        help="Experiment description in JSON format as produced by DIALS "
             "(typically '<input_fn>.expt') "
    )
    ap.add_argument(
        "-o", "--output-file",
        default='exptinfo.cif',
        type=Path,
        help="File name for the imgCIF output"
    )
    ap.add_argument(
        "--url",
        nargs="+",
        help="Full URL of archive, or one archive per scan, in order",
    )
    ap.add_argument(
        "--url-base",
        nargs="+",
        help="Individual image files can be downloaded relative to this base URL",
        metavar="url",
    )
    ap.add_argument(
        "--dir",
        type=Path,
        help="Local folder equivalent to unpacked archive(s) or URL base"
    )
    ap.add_argument(
        "-f", "--format",
        help = "Format of image files, should be one listed in imgCIF dictionary"
    )
    ap.add_argument(
        "-z", "--archive-type",
        help = "Type of overall archive, should be of type listed in imgCIF dictionary"
    )
    ap.add_argument(
        '--overload-value',
        help="Pixels with this value or above in the image data will be considered invalid"
    )
    ap.add_argument(
        '--frames-limit', metavar='N', type=int,
        help="Truncate lists to N frames (per scan), to get a preview output. "
             "The result is incomplete, so remove this option again to generate "
             "the full ImgCIF file."
    )
    ap.add_argument(
        '--no-check-format', action='store_true',
        help="Skip dxtbx checking the data file format. Needed if you don't have the "
             "data files which a DIALS .expt file points to."
    )
    args = ap.parse_args(argv)

    return args

def main(argv=None):

    if argv is None:
        argv = sys.argv[1:]

    args = parse_commandline(argv)
    out_fn = args.output_file
    if not out_fn.suffix:
        out_fn = out_fn.with_suffix('.cif')

    frame_limit = np.inf if (args.frames_limit is None) else args.frames_limit

    if args.url:
        if args.url_base:
            raise ValueError("Pass --url or --url-base, not both")
        locations = [ArchiveUrl(u, args.dir, args.archive_type or guess_archive_type(u))
                     for u in args.url]
    elif args.url_base:
        locations = [DirectoryUrl(u) for u in args.url_base]
        print(locations)
    else:
        raise ValueError("--url or --url-base is required")

    if args.input_fn[0].suffix == '.expt':
        assert len(args.input_fn) == 1, "Please pass only 1 .expt file"
        expts = ExperimentListFactory.from_json_file(
            args.input_fn[0], check_format=(not args.no_check_format)
        )
    else:
        print(f"Attempting to parse {len(args.input_fn)} paths using dxtbx")
        expts = ExperimentListFactory.from_filenames(args.input_fn)
        print(f"Read {len(expts)} experiments")



    with out_fn.open('w') as outf:
        make_cif(expts, outf, out_fn.stem, locations,
                 overload_value=args.overload_value, frame_limit=frame_limit)


if __name__ == '__main__':

    main()
