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

import numpy as np
from scipy.spatial.transform import Rotation as R

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

    wl = expt['beam'][0]['wavelength']

    return wl

#=== Geometry ===

def get_axes_info(expt):
    gon_axes = get_gon_axes(expt)
    det_axes = get_det_axes(expt)
    srf_axes = get_srf_axes(expt)
    
    return gon_axes, det_axes, srf_axes


def get_gon_axes(expt):
    """A goniometer in DIALS is a set of fixed axes, one of which rotates.
       If an axis changes direction, that is a new goniometer.
    """

    g_info = expt['goniometer']
    g_dict = g_info[0]
    debug('axes in JSON dict', g_dict)
 
    axis_dict = {}

    if 'names' not in g_dict:  # single axis then
        assert(len(g_info) == 1)
        axis_dict[GONIO_DEFAULT_AXIS] = {
            'axis': g_dict['rotation_axis'],
            'next': '.',
        }
        
    else:
        n_axes = len(g_dict['names'])
        for i in range(n_axes):
            axis_dict[g_dict['names'][i]] = {
                'axis': g_dict['axes'][i],
                'vals': [x['angles'][i] for x in g_info],
                'next': '.' if i == (n_axes-1) else f'{g_dict["names"][i+1]}'
            }
    debug('axes in processed dict', axis_dict)
    
    return axis_dict


def get_det_axes(expt):
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

    d_info = expt['detector']

    # Sanity check 
    #panels = d_info[0]['panels']   # Not used anymore?
    pp = find_perp_panel(d_info[0])
    if pp is None:
        raise AssertionError('Unable to find a panel perpendicular to the beam at tth = 0')

    axis_dict = {}

    # two theta for each detector position
    axis_info = [get_two_theta(det) for det in d_info]

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
    
    dists = [get_distance(x['panels'][pp]) for x in d_info]

    axis_dict['Trans'] = {
        'axis': [0, 0, -1],
        'vals': dists,
        'next': 'Two_Theta' if ('Two_Theta' in axis_dict) else '.',
        'type': 'translation'
    }
    return axis_dict


def get_two_theta(detector):
    """ Calculate the rotation required to make the normal to the module
        parallel to the beam. This assumes that the panel provided is
        perpendicular to the beam at tth = 0.
        <detector> is a single entry i.e. list element under key 'detector'.
    """

    pp = find_perp_panel(detector)

    panel = detector['panels'][pp]
    p_orth = np.cross(panel['fast_axis'], panel['slow_axis'])
    p_onrm = p_orth / np.linalg.norm(p_orth)
    #debug('Normal to surface', p_onrm)

    if p_onrm[2] > 0: #pointing towards sample
        p_onrm *= -1.0

    if np.linalg.norm(p_onrm - [0,0,-1]) < 0.0001:
        return 0.0, None

    rot_obj = R.align_vectors(np.array([0,0,-1]), p_onrm)
    rot_vec = rot_obj[0].as_rotvec(degrees=True)
    tth_angl = np.linalg.norm(rot_vec)
    tth_axis = rot_vec / tth_angl

    return tth_angl, tth_axis


def get_distance(panel):

    # Get projection of a pixel vector onto the normal to the panel

    p_orth = np.cross(panel['fast_axis'], panel['slow_axis'])
    p_onrm = p_orth / np.linalg.norm(p_orth)
    return abs(np.dot(panel['origin'], p_onrm))


def find_perp_panel(d_info):
    """ Find a panel with normal having x component 0
        Returns: the index of the first panel the meets the requirement
    """

    for i, p in enumerate(d_info['panels']):
        p_orth = np.cross(p['fast_axis'], p['slow_axis'])
        p_onrm = p_orth / np.linalg.norm(p_orth)

        if math.isclose(p_onrm[0], 0.0, abs_tol=0.0001):
            # can be rotated about X to zero
            return i

    return None


def get_srf_axes(expt):
    """ Return the axis directions of each panel when tth = 0
    """
    
    d_info = expt['detector'][0]

    axis_dict = {}
    
    tth_angl, tth_axis = get_two_theta(d_info)
    for i, panel in enumerate(d_info['panels'], start=1):
        fast = panel['fast_axis']
        slow = panel['slow_axis']
        origin = panel['origin']
        
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
                                   'pix_size': panel['pixel_size'][0],
                                   'num_pix': panel['image_size'][0],
                                   'prec': 1,
                                   'element': i
        }
        axis_dict[f'ele{i}_y'] = { 'axis': slow,
                                   'next': f'ele{i}_x',
                                   'origin': [0.0, 0.0, 0.0],
                                   'pix_size': panel['pixel_size'][1],
                                   'num_pix': panel['image_size'][1],
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

    for s_ix, e_block in enumerate(expt['experiment']):

        scan_id = f'SCAN0{s_ix+1}'
        debug('Scan ID', scan_id)  # actually not used further within this function

        scan_info = {}

        gonio = expt['goniometer'][e_block['goniometer']] # gonio info that the index in scan info points to
        if 'names' in gonio:
            scan_ax = gonio['names'][gonio['scan_axis']]
        else:
            scan_ax = GONIO_DEFAULT_AXIS

        # get scan information

        s_block = expt['scan'][e_block['scan']]
        start = s_block['oscillation'][0]
        step = s_block['oscillation'][1]
        num_frames = len(s_block['exposure_time'])
        full_range = step * num_frames # to end of final step

        # Store

        scan_info['scan_axis'] = scan_ax
        scan_info['start'] = start
        scan_info['step'] = step
        scan_info['range'] = full_range
        scan_info['gonio_idx'] = e_block['goniometer']
        scan_info['det_idx'] = e_block['detector']
        scan_info['num_frames'] = num_frames
        scan_info['integration_time'] = s_block['exposure_time']
        scan_info['images'] = expt['imageset'][e_block['imageset']]['template']

        scan_list.append(scan_info)
    
    return scan_list 

# === Derived information to prepare external links ===

def gen_external_locations(scan_list, args):
    """ Based on command-line arguments and the scan information collected
        at this point, we create per-scan information to be written out as
        external file links later.
        Returns: a list of image file info dictionaries per scan
    """

    ext_info = []

    for (s_ix, expt) in enumerate(scan_list):
        local_name = expt['images'] # complete local path as in expt
        name_dict = {}
        name_dict['tail'] = find_filename(local_name, args['cut'])
        if args['scans'] is None:
            if args['location'] is not None:
                name_dict['archive'] = args['location']  # ! []
            else:
                name_dict['archive'] = None
                name_dict['tail'] = local_name
        else:
            name_dict['archive'] = args['scans'][s_ix]

        if not args['format']:
            image_type = determine_file_type(name_dict['tail'])
        else:
            image_type = args['format']  # ! []

        if name_dict['archive'] is not None:
            if not args['archive_type']:
                arch_type = determine_arch_type(name_dict['archive'])
            else:
                arch_type = args['archive_type']  # ! []

            name_dict['arch_type'] = arch_type

        name_dict['image_type'] = image_type
        
        ext_info.append(name_dict)

    debug('External name dictionary', name_dict)
    return ext_info


def find_filename(full_name, cutspec):

    a = re.match(cutspec, full_name)
    debug('Match object', a)
    if a is None:
        print(f'Could not find {cutspec} in {full_name}')
    else:
        tl_st = a.span()[0] + len(cutspec)
        debug('Trimmed part to keep', full_name[tl_st:])
        return full_name[tl_st:]

    return full_name


def determine_arch_type(arch_name):

    comps = arch_name.split('.')

    if comps[-1] == 'tgz' or (comps[-2] == 'tar' and comps[-1] == 'gz'):
        return 'TGZ'
    
    if comps[-1] == 'tbz' or (comps[-2] == 'tar' and comps[-1] == 'bz2'):
        return 'TBZ'

    if comps[-1] == 'zip':
        return 'ZIP'

    if comps[-1] == 'txz' or (comps[-2] == 'tar' and comps[-1] == 'xz'):
        return 'TXZ'
    

def determine_file_type(file_name):
    
    comps = file_name.split('.')

    if comps[-1] == 'cbf':
        return 'CBF'
    else:
        print("WARNING: Unable to determine type of image file")
        return '???'

# ============ Output =============

def cif_init(fn: Path):
    cif_header = f"""#\\#CIF_2.0
# CIF converted from DIALS .expt file
# Conversion routine version 0.1
data_{fn.stem}
"""
    with open(fn, 'w') as outf:
        outf.write(cif_header)


def write_beam_info(wl, fn):
    cif_block = f"""
_diffrn_radiation_wavelength.id    1
_diffrn_radiation_wavelength.value {wl}
_diffrn_radiation.type             xray
"""
    with open(fn, 'a') as outf:
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

def write_axis_info(g_axes, d_axes, s_axes, fn):
    """ Write CIF syntax for all axes of the experiment, where axes
        are both from the goniometer and the detector
    """

    loop_header = """
loop_
 _axis.id
 _axis.depends_on
 _axis.equipment
 _axis.type
 _axis.vector[1]
 _axis.vector[2]
 _axis.vector[3]
 _axis.offset[1]
 _axis.offset[2]
 _axis.offset[3]

"""
    with open(fn, 'a') as outf:
        outf.write(loop_header)

        # round values
        # tth = [round(x, digits = 6) for x in d_axes['Two_Theta']['axis']] # not used anywhere?

        for k, v in g_axes.items():
            debug('Output axis now', k)
            outf.write(f"  {k:10}   {v['next']:10}  goniometer  rotation     {v['axis'][0]:8} {v['axis'][1]:8} {v['axis'][2]:8}")
            outf.write("      0.0      0.0      0.0\n")
 
        # !!! Detector distance is currently not written - as well in the Julia reference
        debug('Detector info', d_axes)
        for k, v in d_axes.items():
            debug('Output axis now', k)
            outf.write(f"  {k:10}   {v['next']:10}  detector    {v['type']:11}  {v['axis'][0]:8} {v['axis'][1]:8} {v['axis'][2]:8}")
            outf.write("      0.0      0.0      0.0\n")
 
        for k, v in s_axes.items():
            debug('Output surface axis', k)
            outf.write(f"  {k:10}   {v['next']:10}  detector    translation  {v['axis'][0]:8} {v['axis'][1]:8} {v['axis'][2]:8}")
            outf.write(f" {v['origin'][0]:8} {v['origin'][1]:8} {v['origin'][2]:8}\n")

        outf.write('\n')


def write_array_info(det_name, n_elms, s_axes, d_axes, fn):
    """ Output information about the layout of the pixels. We assume two axes,
        with the first one the fast direction, and that there is no dead space
        between pixels.
    """

    with open(fn, 'a') as outf:

        outf.write(f"""\
_diffrn_detector.id        {det_name}
_diffrn_detector.diffrn_id DIFFRN
""")
    
        outf.write("""
loop_
 _diffrn_detector_element.id
 _diffrn_detector_element.detector_id

""")
        for elm in range(n_elms):
            outf.write(f'  ELEMENT{elm+1}    {det_name}\n')
        outf.write('\n')

        outf.write(cif_loop(
            "_diffrn_detector_axis",
            ["detector_id", "axis_id"],
            [("DETECTOR", ax) for ax in d_axes]
        ))

        outf.write("""
loop_
 _array_structure_list_axis.axis_id
 _array_structure_list_axis.axis_set_id
 _array_structure_list_axis.displacement
 _array_structure_list_axis.displacement_increment

""")

        set_no = 1
        for axis, v in s_axes.items():
            outf.write(f"  {axis}    {set_no}      {v['pix_size']/2}    {v['pix_size']}\n")
            set_no += 1

        outf.write("""
loop_
 _array_structure_list.array_id
 _array_structure_list.axis_set_id
 _array_structure_list.direction
 _array_structure_list.index
 _array_structure_list.precedence
 _array_structure_list.dimension

""")
        set_no = 1
        for axis, v in s_axes.items():
            outf.write(f"  1            {set_no}          increasing              {v['prec']} {v['prec']} {v['num_pix']}\n")
            set_no += 1
        outf.write('\n')


def write_scan_info(scan_list, g_axes, d_axes, fn):
    """ Output scan axis information 
    """

    loop_header = ("""\
loop_
 _diffrn_scan_axis.scan_id
 _diffrn_scan_axis.axis_id
 _diffrn_scan_axis.displacement_start
 _diffrn_scan_axis.displacement_increment
 _diffrn_scan_axis.displacement_range
 _diffrn_scan_axis.angle_start
 _diffrn_scan_axis.angle_increment
 _diffrn_scan_axis.angle_range

""")
    
    with open(fn, 'a') as outf:

        outf.write(loop_header)

        for s_ix, scan in enumerate(scan_list):

            scan_id = f'SCAN0{s_ix+1}'
        
            # get axis setting information
        
            gi = scan['gonio_idx']
            di = scan['det_idx']
        
            for ax, v in g_axes.items():
                if ax == scan['scan_axis']:
                    outf.write(f"  {scan_id} {ax:10}       .       .       . {scan['start']:7.2f} {scan['step']:7.2f} {scan['range']:7.2f}\n")
                else:
                    outf.write(f"  {scan_id} {ax:10}       .       .       . {v['vals'][gi]:7.2f}       0       0\n")

            for ax, v in d_axes.items():
                if ax == "Trans":
                    outf.write(f"  {scan_id} {ax:10} {v['vals'][di]:7.2f}     0.0     0.0       .       .       .\n")
                else:
                    outf.write(f"  {scan_id} {ax:10}       .       .       . {v['vals'][di]:7.2f}     0.0     0.0\n")

            outf.write('\n')

def write_frame_ids(scan_list, fn):

    with open(fn, 'a') as outf:
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
            for f_ix in range(scan['num_frames']):
                exp_time = scan['integration_time']
                rows.append((f"frm{counter}", f"SCAN{s_ix:02}", f_ix + 1, exp_time[f_ix]))
                counter += 1

        outf.write(cif_loop(
            "_diffrn_scan_frame",
            ["frame_id", "scan_id", "frame_number", "integration_time"],
            rows
        ))


def write_frame_images(scan_list, fn):
    """ Link frames to binary images
        TODO: Match array and element names
    """
    
    with open(fn, 'a') as outf:
        rows = []
        counter = 1
        for scan in scan_list:
            for _ in range(scan['num_frames']):
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


def write_external_locations(ext_info, scans, fn):
    """ External locations must be of uniform type, and organised in scan order.
    """

    with open(fn, 'a') as outf:
        outf.write("""\
loop_
 _array_data_external_data.id
 _array_data_external_data.format
 _array_data_external_data.uri
""")
        if 'arch_type' in ext_info[0]:
            outf.write(' _array_data_external_data.archive_format\n')
            outf.write(' _array_data_external_data.archive_path\n')
        outf.write('\n')

        counter = 1
        for (s_ix, extf) in enumerate(ext_info):
            for fr_ix in range(1, scans[s_ix]['num_frames'] + 1):
                outf.write(f"  {counter}   {extf['image_type']} ")
                location = encode_scan_step(extf['tail'], fr_ix)
                if 'arch_type' not in extf:
                    outf.write(f'  {location}\n')
                else:
                    outf.write(f"  {extf['archive']}  {extf['arch_type']}  {location}\n")
                counter += 1


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
        "-s", "--scans",
        nargs = '+',
        help = "Full URL of archive for each scan, in order",
        metavar = "url"
    )
    ap.add_argument(    
        "-l", "--location",
        help = "URL of archive containing all images (use -s for multiple archives)",
        metavar = "url",
    )
    ap.add_argument(
        "-c", "--cut",
        metavar = "match",
        help = "All characters in local file name following <match> refer to location within archive"
    )
    ap.add_argument(
        "-f", "--format",
        help = "Format of image files, should be one listed in imgCIF dictionary"
    )
    ap.add_argument(
        "-z", "--archive-type",
        help = "Type of overall archive, should be of type listed in imgCIF dictionary"
    )
    args = ap.parse_args(argv)

    return args

def main():

    args = parse_commandline(sys.argv[1:])
    out_fn = args.output_file
    if not out_fn.suffix:
        out_fn = out_fn.with_suffix('.cif')

    cif_init(out_fn)
    expt = extract_raw_info(args.input_fn)

    wl = get_beam_info(expt)
    write_beam_info(wl, out_fn)

    g_ax, d_ax, s_ax = get_axes_info(expt)
    write_axis_info(g_ax, d_ax, s_ax, out_fn)

    write_array_info('DETECTOR',
                     len(expt['detector'][0]['panels']),
                     s_ax, d_ax, out_fn)

    scans = get_scan_info(expt)
    write_scan_info(scans, g_ax, d_ax, out_fn)
    write_frame_ids(scans, out_fn)
    write_frame_images(scans, out_fn)

    ext_info = gen_external_locations(scans, vars(args)) 
    write_external_locations(ext_info, scans, out_fn)


if __name__ == '__main__':

    main()

