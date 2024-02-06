"""This module defines an extractor class that allows to extract information
from an expt file created with DIALS from various original input.
"""

from inspect import getsourcefile
import json
import numpy as np
import os
import re
from scipy.spatial.transform import Rotation as R
import sys
import yaml
from imgCIF_Creator.output_creator import imgcif_creator
from . import extractor_interface, full_cbf, extractor_utils


class Extractor(extractor_interface.ExtractorInterface):
    """See also documentation of the init method.

    Args:
        extractor_interface (class): the interface that must be implemented by
            every extractor class
    """

    def __init__(self, filename, _) -> None:
        """This extractor allows to extract the scan and setup information from
        expt files. When an instance of the extractor is initialized
        then the information is attempted to be extracted and stored in class
        attributes. The extractor provides public methods to make this information
        accessible.

        Args:
            filename (str): name of the expt file containing information in JSON to
                be extracted.
        """

        self._raw_dict = self._ingest_json(filename)
        #print(self._raw_dict, '\n\n')

        assert(len(self._raw_dict['scan']) == len(self._raw_dict['goniometer']))

        _unique_scans = {}
        _scanax_gonio = {}
        _wavelength = {}
        _det_origin = {}
        _pixel_size = {}
        for id, scan_info in enumerate(self._raw_dict['scan']):
            _unique_scans[f'{id+1:02d}'] = scan_info
            _scanax_gonio[f'{id+1:02d}'] = self._raw_dict['goniometer'][id]
            _wavelength[f'{id+1:02d}'] = self._raw_dict['beam'][id]['wavelength']
            _det_origin[f'{id+1:02d}'] = \
                self._raw_dict['detector'][id]['panels'][0]['origin']
            _pixel_size[f'{id+1:02d}'] = \
                self._raw_dict['detector'][id]['panels'][0]['pixel_size']

        print(f'{len(_unique_scans.keys())} scan(s) found')

        self._scan_info_expt(_unique_scans, _scanax_gonio, _wavelength,
                                    _det_origin, _pixel_size)

        self._resources_path = os.path.abspath(getsourcefile(lambda: 0)).replace(
            'information_extractors/dials_expt.py', 'resources/')

        with open(f"{self._resources_path}user_input.yaml", 'r') as stream:
            try:
                input_options = yaml.safe_load(stream)
                self._facility_options = input_options['facility']['options']
            except yaml.YAMLError as error:
                print(error)

    def get_scan_settings_info(self):
        """Return pre-collected data from the self._scan_info_expt() helper
        function.
        NOTE: in the cbf_smv template, a prune function was applied, and
        frame-type info returned as well.
        """
        print('# Entering scan-settings info getter')

        return self.scan_info
        

    def get_axes_position_dict(self, expt_gonio_axes, n_frames, scan_incr):
        """Re-arrange the multi-axis dictionary of the expt input (features as
        keys) to a dictionary of {name: angle} type with axes names as keys,
        for those names found - no 2theta (!), kappa 
        """
        axes_settings = {}
        _index = int(expt_gonio_axes['scan_axis'])
        _axes_names  = [name.split('_')[-1].lower() for name in expt_gonio_axes['names']]
        _axes_angles = expt_gonio_axes['angles']
        _axes_angles[_index] += round((n_frames - 1) * scan_incr, 10)
        for i, name in enumerate(_axes_names):
            axes_settings[name] = _axes_angles[i]
        return axes_settings

    def _scan_info_expt(self, _scan_frame_info, _scan_gonio_axes,
                               _wavelength, _det_origin, _pixel_size):
        """Assemble information about the scans, this is a dictionary containing
        the starting point settings of the axes and the details of each scan.

        Args:
            _scan_frame_info: dictionary holding (N scan) sub-dictionaries
                              with frame info
            _scan_gonio_axes: dictionary holding (N scan) sub-dictionaries
                              with goniometer axes settings
            _wavelength: photon wavelength as in 'beam' sub-dict of the input
            _det_origin: detector origin relative to the interaction point
                         (adding detector distance and beam center), as in
                         'detector/panel' sub-dict of the input
            _pixel_size: detector pixel size as in 'detector/panel' sub-dict
        """

        self.scan_info = {}

        for scan in _scan_frame_info.keys():
            img_num_range = _scan_frame_info[scan]['image_range']
            n_frames = img_num_range[1] - img_num_range[0] + 1
            scan_ax_index = _scan_gonio_axes[scan]['scan_axis']
            scan_ax_name = \
            _scan_gonio_axes[scan]['names'][scan_ax_index].split('_')[1].lower()
            scan_ax_start = _scan_gonio_axes[scan]['angles'][scan_ax_index]
            osc_range = _scan_frame_info[scan]['oscillation']
            scan_incr = osc_range[1] - osc_range[0]
            """ DIALS produces individual exposure times for every frame;
            we assume this is constant and take the first as global value"""
            exposure = _scan_frame_info[scan]['exposure_time'][0]

            scan_details = {"frames" : n_frames,
                            "axis" : scan_ax_name,
                            "incr" : scan_incr,
                            "time" : exposure,
                            "start" : scan_ax_start,
                            # because of 0.1*137 = 13.700000000000001 we round
                            "range" : round(scan_incr * n_frames, 10),
                            "wavelength" : _wavelength[scan],
                            "x_pixel_size" : _pixel_size[scan][0],
                            "y_pixel_size" : _pixel_size[scan][1],
                            "mini_header" : 'none'  # to be clarified
                            }
            axes_settings = self.get_axes_position_dict(_scan_gonio_axes[scan], n_frames, scan_incr)
            axes_settings['distance'] = _det_origin[scan][2]
            # DEBUG START
            #print('# DEBUG INFO # ')
            #print(axes_settings)
            #print(scan_details)
            # DEBUG END

            self.scan_info[scan] = (axes_settings, scan_details)


    def get_source_info(self):
        """Return the information about the facility and beamline or the instrument,
        model and location. Cif block: _diffrn_source

        Returns:
            dict: a dictionary containing the information about the source
        """

        print('# Entering source info getter')

        facility = extractor_utils.name_contained(self._raw_dict, 'identifier',
                                                  self._facility_options)
        beamline = None
        manufacturer = None
        model = None
        location = None

        source_info = {'beamline' : beamline,
                       'facility' : facility,
                       'manufacturer' : manufacturer,
                       'model' : model,
                       'location' : location}

        return source_info
    

    def _stack_gonio_axes_from_scans(self):
        """Return a value for the dictionary 'gonio_axes_found', which is
           a tuple of lists: ([gonio_scan_axes], [rotation_senses])
        """
        _ax_names = []
        _ax_sense = []
        for scan in self.scan_info.keys():
            # tuple element [1] is the 'scan_details' dictionary
            _ax_names.append(self.scan_info[scan][1]['axis'])
            _ax_sense.append('c')
        return (_ax_names, _ax_sense)

    """
    get_two_theta(detector)

    Work out the rotation required to make the normal to
    the module parallel to the beam. This assumes that
    the panel provided is perpendicular to the beam at
    tth = 0. `detector` is a single "detector" entry.

    JULIA CODE start ------------------------------------

    get_two_theta(detector) = begin

        pp = find_perp_panel(detector)

        panel = detector["panels"][pp]
        normal = LinearAlgebra.normalize(cross(panel["fast_axis"], panel["slow_axis"]))

        @debug "Normal to surface" normal
        if norm(normal - [0,0,1]) < 0.0001
            return 0.0, nothing
        end

        if normal[3] > 0 #pointing towards sample 
            normal = normal * -1.0
        end

        rb = rotation_between([0,0,-1],normal)
        tth = rad2deg(rotation_angle(rb))
        axis = rotation_axis(rb)

        return tth, axis
    end

    JULIA CODE end ----------------------------------------
    """

    def _get_detector_panels(self):
        """Extract the per-panel detector frame vectors (ss, fs) as in the
           input dict (typically one such panel section per scan)

           Returns: list of 2-tuples of 3-tuples, where list is over scans;
                    outer tuple (flax, slax); inner tuple is vector (x,y,z)
        """
        _frame_vectors = []
        det_info = self._raw_dict['detector']
        print(f'detector stack contains {len(det_info)} entries')
        for det in det_info:
            fsax = tuple(det['panels'][0]['fast_axis'])
            slax = tuple(det['panels'][0]['slow_axis'])
            _frame_vectors.append((fsax, slax))

        return _frame_vectors

    def _get_two_theta(self, panel):
        """For a given pair of detector frame axes (fast, slow) in
           Dials expt notation, find the rotation operation from the
           panel-normal vector to the beam vector, usually [0,0,1],
           and return the axis-angle description of that rotation

           Args:
           - panel: a 2-tuple (fsax, slax) of 3-tuples (x,y,z)

           Returns: an unpacked tuple: axis (orientiation vector), angle
        """
        fsax, slax = panel
        #print('# input DET frame axes', fsax, slax)
        p_orth = np.cross(fsax, slax)
        #print('# plane ortho', p_orth)
        p_norm = p_orth / np.linalg.norm(p_orth)
        print('# plane norm', p_norm)
        print('# delta vec', p_norm - np.array([0,0,-1]))
        print('# norm of delta', np.linalg.norm(p_norm - np.array([0,0,-1])))
        if np.linalg.norm(p_norm - np.array([0,0,-1])) < 0.001:
            return (0,0,0), 0.0
        if p_norm[2] > 0:
            p_norm *= -1.0
        rot_obj = R.align_vectors(np.array([0,0,-1]), p_norm)
        rot_vec = rot_obj[0].as_rotvec(degrees=True)
        rot_ang = np.linalg.norm(rot_vec)
        rot_axs = rot_vec / rot_ang
        print('# 2-theta axis', rot_axs, 'angle', rot_ang)
        return rot_axs, rot_ang
    
    def _stack_detrot_axes_from_scans(self):
        """Return a value for the dictionary 'det_rot_axes_found', which is
           a tuple of lists: ([rotation_axes], [rotation_senses])
           ! BEFORE:
           ! This is setting constant fill values, because 'Detector_2theta'
           ! from the mini-CBF header is not taken over into .expt
           ! ADAPTATION:
           ! replace fill value with proper value from detector plane normal;
           ! new function '_get_two_theta' ported from Julia
        """
        _n  = len(self.scan_info)
        # get the unique items in detector info
        panel_axes = self._get_detector_panels()
        print(panel_axes)
        #exit()
        # convert panel axes to relative (plane-normal) orientation wrt. beam
        panel_2theta_ang = []
        panel_2theta_axs = []
        for p in panel_axes:
            axs, ang = self._get_two_theta(p)
            panel_2theta_ang.append(ang)
            panel_2theta_axs.append(axs)
        # map (reduce or expand) to scans list: TODO
        scan_2theta_ang = []
        scan_2theta_axs = []
        # map_detconfig_to_scan()
        scan_2theta_ang.append(panel_2theta_ang[1])
        scan_2theta_axs.append(panel_2theta_axs[1])
        #return (['detector_2theta' for _ in range(_n)], ['c' for _ in range(_n)])
        return (['detector_2theta' for _ in range(_n)], [scan_2theta_ang[_] for _ in range(_n)])
    

    def _stack_det_trans_from_scans(self):
        """Return a value for the dictionary 'det_trans_axes_found', which is
           a simple list: [tranlation_axes]
        """
        _dist_axes = []   # the 'distance axis' ids
        _distances = []   # the distance values
        for scan in self.scan_info.keys():
            # tuple element [0] is the 'axes_settings' dictionary
            _dist_axes.append('trans')
            _distances.append(self.scan_info[scan][0]['distance'])
        return (_dist_axes, _distances)


    def get_axes_info(self):
        """Return the information about the axes settings. Cif block: _axis

        Returns:
            dict: a dictionary containing the information about the axes settings
        """

        print('# Entering axes info getter')

        gonio_axes = self._stack_gonio_axes_from_scans()
        det_rot_axes = self._stack_detrot_axes_from_scans()
        det_trans = self._stack_det_trans_from_scans()

        axes_info = {'axes' : None}
        axes_info['gonio_axes_found'] = gonio_axes
        axes_info['det_rot_axes_found'] = det_rot_axes
        axes_info['det_trans_axes_found'] = det_trans
        print('DEBUG - function "get_axes_info" return content:')
        print(axes_info)
        return axes_info


    def get_array_info(self):
        """Return the information about the array. Cif block: _array_structure_list_axis
        and _array_structure_list

        Returns:
            dict: a dictionary containing the information about the array
        """

        x_px = self.scan_info['01'][1]['x_pixel_size']
        y_px = self.scan_info['01'][1]['y_pixel_size']
        array_dimension = self._raw_dict['detector'][0]['panels'][0]['image_size']
        pixel_size = [x_px, y_px]

        array_info = {
            'axis_id' : None,
            'axis_set_id': None,
            'pixel_size' : pixel_size,
            'array_id' : None,
            'array_index' : None,
            'array_dimension' : array_dimension,
            'array_direction' : None,
            'array_precedence' : None,
        }
        return array_info


    def get_detector_info(self):
        """Return the information about the detector. Cif block: _diffrn_detector
        and _diffrn_detector_axis.

        Returns:
            dict: a dictionary containing the information about the detector
        """

        print('# Entering detector info getter')

        detector_id = self._raw_dict['detector'][0]['panels'][0]['identifier']
        number_of_axes = len(self._raw_dict['detector'][0]['panels'][0]['image_size'])

        detector_info = {
            'detector_id' : detector_id,
            'number_of_axes' : number_of_axes,
            'axis_id' : None,
            'detector_axis_id' : None
        }
        return detector_info


    def get_radiation_info(self):
        """Return the information about the wavelength an type of radiation.
        Cif block: _diffrn_radiation and _diffrn_radiation_wavelength

        Returns:
           dict: a dictionary containing the information about the radiation
        """

        print('# Entering radiation info getter')

        rad_type = None
        wavelength = self.scan_info['01'][1]['wavelength']

        return {'rad_type' : rad_type,
                'wavelength' : wavelength}


    def get_misc_info(self):
        """Return the information that was found about the doi and the array
        intensities overload.

        Returns:
            dict: a dictionary containing the doi and the array intensities overload
        """

        print('# Entering misc info getter')

        doi = None
        overload = self._raw_dict['detector'][0]['panels'][0]['trusted_range'][1]
        temperature = None
        return {'doi' : doi,
                'overload' : overload,
                'temperature': temperature,
                }


    def _ingest_json(self, filename):
        """Import the JSON content of an expt file into a temporary dictionary

        Args:
            filename (str): name of the expt file containing JSON information

        Returns:
            metadata_dict: JSON content parsed to a nested Python dictionary
        """

        metadata_dict = {}
        if not os.path.exists(filename):
            print(f'Could not open input file {filename}! Aborting!')
            sys.exit()
        with open(filename, 'r') as f:
            try:
                metadata_dict = json.load(f)
            except json.decoder.JSONDecodeError:
                print('Could not recognize/decode/interpret JSON format.')
        return metadata_dict
