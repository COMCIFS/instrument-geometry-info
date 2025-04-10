"""
Ported from 
https://github.com/COMCIFS/instrument-geometry-info/blob/main/Tools/dials_expt_to_imgcif.jl
Orignal author: Dr. James Hester, ANSTO, Lucas Heights, Australia 
"""

import json
import math
import os
import re
import sys
from argparse import ArgumentParser
from pathlib import Path

import h5py
import numpy as np
from dxtbx.model.experiment_list import ExperimentListFactory
from dxtbx.model import MultiAxisGoniometer
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


def sanity_check(js_info):
    """ Check for all the things that we assume
    """

    # Detector checks
    
    d_info = js_info['detector']

    panel_count = [len(x['panels']) for x in d_info]
    #debug('Panel numbers across detector entries', pc)
    assert len(set(panel_count)) == 1

    # Assume if names are the same, it is the same panel

    for i in range(panel_count[0]):
        panel_names = [x['panels'][i]['name'] for x in d_info]
        assert len(set(panel_names)) == 1


#=== Raw input parsing from JSON ===

def extract_raw_info(filename):

    if not os.path.exists(filename):
        print(f'Could not open input file "{filename}": Aborting!')
        sys.exit()

    with open(filename, 'r') as f:
        try:
            expt_dict = json.load(f)
            sanity_check(expt_dict)
        except json.decoder.JSONDecodeError:
            print('Could not recognize/decode/interpret JSON format.')

    return expt_dict


#=== Radiation ===

def get_beam_info(expt):

    wl = expt[0].beam.get_wavelength()

    return wl

#=== Geometry ===

def get_axes_info(expt):
    gon_axes = get_gon_axes(expt)

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
        np.testing.assert_allclose(
            axis_rotation.apply(primary_axis), [1., 0., 0.], atol=1e-8
        )

    gon_axes = {k: v | {'axis': axis_rotation.apply(v['axis'])}
                for k, v in gon_axes.items()}

    det_axes = get_det_axes(expt, axis_rotation)
    srf_axes = get_srf_axes(expt, axis_rotation)
    
    return gon_axes, det_axes, srf_axes


def get_gon_axes(expt):
    """A goniometer in DIALS is a set of fixed axes, one of which rotates.
       If an axis changes direction, that is a new goniometer.
    """

    gon0 = expt[0].goniometer
    # g_info = expt['goniometer']
    # g_dict = g_info[0]
    #debug('axes in JSON dict', g_dict)
 
    axis_dict = {}

    if isinstance(gon0, MultiAxisGoniometer):
        names = gon0.get_names()
        n_axes = len(names)
        for i in range(n_axes):
            axis_dict[names[i]] = {
                'axis': gon0.get_axes()[i],
                'vals': [e.goniometer.get_angles()[i] for e in expt],
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


def get_det_axes(expt, axis_rotation):
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

    d_info = expt[0].detector

    # Sanity check 
    #panels = d_info[0]['panels']   # Not used anymore?
    pp = find_perp_panel(d_info, axis_rotation)
    if pp is None:
        raise AssertionError('Unable to find a panel perpendicular to the beam at tth = 0')

    axis_dict = {}

    # two theta for each detector position
    axis_info = [get_two_theta(e.detector, axis_rotation) for e in expt]

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
    
    dists = [get_distance(list(e.detector.iter_panels())[pp], axis_rotation)
             for e in expt]

    axis_dict['Trans'] = {
        'axis': [0, 0, -1],
        'vals': dists,
        'next': 'Two_Theta' if ('Two_Theta' in axis_dict) else '.',
        'type': 'translation'
    }
    return axis_dict


def get_two_theta(detector, axis_rotation):
    """ Calculate the rotation required to make the normal to the module
        parallel to the beam. This assumes that the panel provided is
        perpendicular to the beam at tth = 0.
        <detector> is a single entry i.e. list element under key 'detector'.
    """

    pp = find_perp_panel(detector, axis_rotation)

    panel = list(detector.iter_panels())[pp]
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


def get_distance(panel, axis_rotation):

    # Get projection of a pixel vector onto the normal to the panel

    p_orth = np.cross(
        axis_rotation.apply(panel.get_fast_axis()),
        axis_rotation.apply(panel.get_slow_axis())
    )
    p_onrm = p_orth / np.linalg.norm(p_orth)
    origin = axis_rotation.apply(panel.get_origin())
    return abs(np.dot(origin, p_onrm))


def find_perp_panel(d_info, axis_rotation):
    """ Find a panel with normal having x component 0
        Returns: the index of the first panel the meets the requirement
    """

    for i, p in enumerate(d_info.iter_panels()):
        p_orth = np.cross(
            axis_rotation.apply(p.get_fast_axis()),
            axis_rotation.apply(p.get_slow_axis())
        )
        p_onrm = p_orth / np.linalg.norm(p_orth)

        if math.isclose(p_onrm[0], 0.0, abs_tol=0.0001):
            # can be rotated about X to zero
            return i

    return None


def get_srf_axes(expt, axis_rotation):
    """ Return the axis directions of each panel when tth = 0
    """
    
    d_info = expt[0].detector

    axis_dict = {}
    
    tth_angl, tth_axis = get_two_theta(d_info, axis_rotation)
    for i, panel in enumerate(d_info.iter_panels(), start=1):
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
        
        axis_dict[f'ele{i}_x'] = { 'axis': fast,
                                   'next': "Trans",
                                   'origin': origin,
                                   'pix_size': panel.get_pixel_size()[0],
                                   'num_pix': panel.get_image_size()[0],
                                   'prec': 1,
                                   'element': i
        }
        axis_dict[f'ele{i}_y'] = { 'axis': slow,
                                   'next': f'ele{i}_x',
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
def get_scan_info(expt):
    """ Returns: list of dictionaries for each scan
    """
    scan_list = []

    for s_ix, e_block in enumerate(expt):

        scan_id = f'SCAN0{s_ix+1}'
        debug('Scan ID', scan_id)  # actually not used further within this function

        scan_info = {}

        # gonio = expt['goniometer'][e_block['goniometer']] # gonio info that the index in scan info points to
        if isinstance(e_block.goniometer, MultiAxisGoniometer):
            gonio_names = e_block.goniometer.get_names()
            scan_ax = gonio_names[e_block.goniometer.get_scan_axis()]
        else:
            scan_ax = GONIO_DEFAULT_AXIS

        # get scan information

        # s_block = expt['scan'][e_block['scan']]
        exposure_times = e_block.scan.get_exposure_times()
        num_frames = len(exposure_times)
        start, step = e_block.scan.get_oscillation()
        full_range = step * num_frames # to end of final step

        # Store

        scan_info['scan_axis'] = scan_ax
        scan_info['start'] = start
        scan_info['step'] = step
        scan_info['range'] = full_range
        scan_info['num_frames'] = num_frames
        scan_info['integration_time'] = exposure_times
        scan_info['images'] = e_block.imageset.get_template()

        scan_list.append(scan_info)
    
    return scan_list 

# === Derived information to prepare external links ===

def gen_external_locations(scan_list, args):
    """ Based on command-line arguments and the scan information collected
        at this point, we create per-scan information to be written out as
        external file links later.
        Returns: a list of image file info dictionaries per scan
    """

    n_scans = len(scan_list)
    url_bases = urls = None
    if args.url_base:
        if len(args.url_base) == 1:
            url_bases = args.url_base * n_scans
        elif len(args.url_base) == n_scans:
            url_bases = args.url_base
        else:
            raise ValueError(
                f"--url-bases should have 1 parameter or 1 per scan ({n_scans})"
            )
    elif args.url:
        if len(args.url) == 1:
            urls = args.url * n_scans
        elif len(args.url) == n_scans:
            urls = args.url
        else:
            raise ValueError(f"--url should have 1 parameter or 1 per scan ({n_scans})")
    else:
        raise ValueError("--url or --url-base is required")

    ext_info = []

    for (s_ix, expt) in enumerate(scan_list):
        local_name = Path(expt['images']) # complete local path as in expt
        template_rel_path = local_name.relative_to(args.dir)

        fmt = args.format or guess_file_type(template_rel_path.name)

        if fmt == 'HDF5':
            total_n_frames = 0
            for file_rel_path, obj_path, n in find_hdf5_images(local_name, args.dir):
                d = {'format': fmt, 'num_frames': n, 'path': obj_path}
                if url_bases is not None:
                    ub = url_bases[s_ix]
                    d['uri_template'] = ub.rstrip('/') + '/' + str(file_rel_path)
                else:
                    d['uri'] = url = urls[s_ix]
                    d['archive_format'] = args.archive_type or guess_archive_type(url)
                    d['archive_path_template'] = str(file_rel_path)
                total_n_frames += n
                ext_info.append(d)
                print(f"{n} images in file {file_rel_path}")
            assert total_n_frames == expt['num_frames']
        else:
            d = {'format': fmt, 'num_frames': expt['num_frames']}
            if url_bases is not None:
                ub = url_bases[s_ix]
                d['uri_template'] = ub.rstrip('/') + '/' + str(template_rel_path)
            else:
                d['uri'] = url = urls[s_ix]
                d['archive_format'] = args.archive_type or guess_archive_type(url)
                d['archive_path_template'] = str(template_rel_path)
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
    

def guess_file_type(name: str):
    if name.endswith('.cbf'):
        return 'CBF'
    elif name.endswith(('.h5', '.nxs')):
        return 'HDF5'
    else:
        print(f"WARNING: Unable to determine type of image file ({name})")
        return '???'


def find_hdf5_images(master_path, dir):
    master = h5py.File(master_path, 'r')
    data_grp = master['/entry/data']
    for name in sorted(data_grp):
        if not re.match(r'data_\d+$', name):
            continue

        link = data_grp.get(name, getlink=True)
        dset = data_grp[name]
        if isinstance(link, h5py.ExternalLink):
            file_path = (master_path.parent / link.filename).relative_to(dir)
            obj_path = link.path
        else:
            file_path = master_path.relative_to(dir)
            obj_path = dset.name

        yield file_path, obj_path, dset.shape[0]


# ============ Output =============


def write_beam_info(wl, outf):
    cif_block = f"""
_diffrn_radiation_wavelength.id    1
_diffrn_radiation_wavelength.value {wl}
_diffrn_radiation.type             xray

"""
    outf.write(cif_block)

def cif_loop(base_name: str, fields: list, rows) -> str:
    """Assemble a loop_ table ready to be written to a CIF file"""
    for i, row in enumerate(rows, start=1):
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



def write_scan_info(scan_list, g_axes, d_axes, outf):
    """ Output scan axis information 
    """
    fields = [
        "scan_id", "axis_id", "displacement_start", "displacement_increment",
        "displacement_range", "angle_start", "angle_increment", "angle_range"
    ]
    rows = []
    fmt = lambda v: format(v, '.2f')

    for s_ix, scan in enumerate(scan_list):

        scan_id = f'SCAN0{s_ix+1}'

        # get axis setting information

        for ax, v in g_axes.items():
            if ax == scan['scan_axis']:
                rows.append((
                    scan_id, ax, ".", ".", ".", fmt(scan['start']), fmt(scan['step']), fmt(scan['range'])
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

def write_frame_ids(scan_list, outf, scan_frame_limit=np.inf):
    rows = []
    counter = 1
    for s_ix, scan in enumerate(scan_list, start=1):
        end_cnt = counter + scan['num_frames'] - 1
        rows.append((f"SCAN{s_ix:02}", f"frm{counter}", f"frm{end_cnt}", scan['num_frames']))
        counter = end_cnt + 1

    outf.write(cif_loop(
        "_diffrn_scan",
        ["id", "frame_id_start", "frame_id_end", "frames"],
        rows
    ))

    rows = []
    counter = 1
    for s_ix, scan in enumerate(scan_list, start=1):
        for f_ix in range(min(scan['num_frames'], scan_frame_limit)):
            exp_time = scan['integration_time']
            rows.append((f"frm{counter}", f"SCAN{s_ix:02}", f_ix + 1, exp_time[f_ix]))
            counter += 1

    outf.write(cif_loop(
        "_diffrn_scan_frame",
        ["frame_id", "scan_id", "frame_number", "integration_time"],
        rows
    ))


def write_frame_images(scan_list, outf, scan_frame_limit=np.inf):
    """ Link frames to binary images
        TODO: Match array and element names
    """
    rows = []
    counter = 1
    for scan in scan_list:
        for f_ix in range(min(scan['num_frames'], scan_frame_limit)):
            rows.append((f"frm{counter}", "ELEMENT", "IMAGE", counter))
            counter += 1

    outf.write(cif_loop(
        "_diffrn_data_frame",
        ["id", "detector_element_id", "array_id", "binary_id"],
        rows
    ))

    # Now link images with external locations

    outf.write(cif_loop(
        "_array_data",
        ["array_id", "binary_id", "external_data_id"],
        [("IMAGE", i, i) for i in range(1, counter)]
    ))


def write_external_locations(ext_info, scans, outf, scan_frame_limit=np.inf):
    """ External locations must be of uniform type, and organised in scan order.
    """
    fields = ['id', 'format', 'uri']
    if 'archive_format' in ext_info[0]:
        fields += ['archive_format', 'archive_path']
    if ext_info[0]['format'] == 'HDF5':
        fields += ['path', 'frame']

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
                r += [extf['path'], fr_ix]
            rows.append(r)
            counter += 1

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


# ============= main ==============

def parse_commandline(argv):

    ap = ArgumentParser(prog="dials2imgcif")
    ap.add_argument(
        "input_fn",
        type=Path,
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
    args = ap.parse_args(argv)

    return args

def main():

    args = parse_commandline(sys.argv[1:])
    out_fn = args.output_file
    if not out_fn.suffix:
        out_fn = out_fn.with_suffix('.cif')

    frame_limit = np.inf if (args.frames_limit is None) else args.frames_limit

    with out_fn.open('w') as outf:
        outf.write(CIF_HEADER.format(name=out_fn.stem))
        #expt = extract_raw_info(args.input_fn)
        expts = ExperimentListFactory.from_json_file(args.input_fn)

        wl = get_beam_info(expts)
        write_beam_info(wl, outf)

        g_ax, d_ax, s_ax = get_axes_info(expts)
        write_axis_info(g_ax, d_ax, s_ax, outf)

        write_array_info('DETECTOR',
                         len(list(expts[0].detector.iter_panels())),
                         s_ax, d_ax, outf, args.overload_value)

        scans = get_scan_info(expts)
        write_scan_info(scans, g_ax, d_ax, outf)
        write_frame_ids(scans, outf, frame_limit)
        write_frame_images(scans, outf, frame_limit)

        ext_info = gen_external_locations(scans, args)
        write_external_locations(ext_info, scans, outf, frame_limit)


if __name__ == '__main__':

    main()

