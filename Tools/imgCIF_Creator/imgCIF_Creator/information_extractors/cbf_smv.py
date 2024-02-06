"""This module defines an extractor class that allows to extract information
from an cbf or smv file with an mini header.
"""

import os
import re
import sys
import numpy as np
from imgCIF_Creator.output_creator import imgcif_creator
from . import extractor_interface, full_cbf, extractor_utils


class Extractor(extractor_interface.ExtractorInterface):
    """See also documentation of the init method.

    Args:
        extractor_interface (class): the interface that must be implemented by
            every extractor class
    """

    def __init__(self, directory, stem) -> None:
        """This extractor allows to extract the scan and setup information from
        cbf and smv files. When an instance of the extractor is initialized
        then the information is attempted to be extracted and stored in class
        attributes. The extractor provides public methods to make this information
        accessible.

        Args:
            directory (str): the directory where the extractor tries to extract
                the information
            stem (str): constant portion of a frame file name to help determine the
                scan/frame file naming convention
        """

        self._unique_scans, self.all_frames = \
            self._get_scans_and_frames(directory, stem=stem)

        # retrieve mini header info
        # only mini header info contains scan details regarding increment etc
        self._scan_info_mini_header, self.frame_type = \
            self._get_scan_info_mini_header(directory, self._unique_scans, self.all_frames)
        self._first_scan = sorted(self._scan_info_mini_header.keys())[0]
        self.first_mini_header = \
            self._scan_info_mini_header[self._first_scan][1]['mini_header']

        # retrieve full header info
        full_header_is_empty = True
        if self.frame_type == "CBF":
            self._scan_info_full_header = \
                self._get_info_full_header(directory, self._unique_scans, self.all_frames)

            full_header_is_empty = self._scan_info_full_header[self._first_scan].keys() == []

        if full_header_is_empty:
            self._data_name = None
            self._full_header_dict = {}
        else:
            self._data_name = \
                list(self._scan_info_full_header[self._first_scan].keys())[0]
            self._full_header_dict = \
                self._scan_info_full_header[self._first_scan][self._data_name]


    def get_all_frames(self):
        """Get a dictionary containing an entry for each frame with corresponding
        file name.
        Format:
        {('scan name', frame number): {'filename': 'ciclohexano3_010001.cbf'}, ...}

        Returns:
            dict: a dictionary containing all frames and their corresponding file
        """

        return self.all_frames


    def get_misc_info(self):
        """Return the information that was found about the doi and the array
        intensities overload.

        Returns:
            dict: a dictionary containing the array intensities overload
        """

        print('# Entering misc info getter')

        doi = self._full_header_dict.get('_database.dataset_doi')
        overload = self._full_header_dict.get('_array_intensities.overload')
        temperature = self._full_header_dict.get('_diffrn.ambient_temperature')

        if overload is None:
            overload, _ = self._get_cbf_header_values(
                self.first_mini_header, 'count_cutoff', with_unit=False)
            if overload is not None:
                overload = int(overload)

        if temperature is None:
            temperature, unit = self._get_cbf_header_values(
                self.first_mini_header, 'temperature', with_unit=True)
            if unit is not None and 'k' in unit.lower():
                temperature -= 273.15

        return {'doi' : doi,
                'overload' : overload,
                'temperature': temperature,
                }


    def get_source_info(self):
        """Return the information about the facility and beamline or the instrument,
        model and location. Cif block: _diffrn_source

        Returns:
            dict: a dictionary containing the information about the source
        """

        print('# Entering source info getter')

        facility = None
        beamline = None

        # TODO can it appear in the mini header?
        block_ids = ['_diffrn_source.diffrn_id', '_diffrn.id']
        for b_id in block_ids:
            block_id = self._lists_to_values(self._full_header_dict.get(b_id))
            if block_id is not None:
                beamline = block_id.split('_')[-1]

        # check beamline is the same?
        source_string = self._lists_to_values(
            self._full_header_dict.get('_diffrn_source.type'))
        if source_string is not None:
            if 'beamline' in source_string:
                splitter = 'beamline'
            elif 'Beamline' in source_string:
                splitter = 'Beamline'
            else:
                splitter = None
            if splitter is not None:
                facility, beamline_source = source_string.split(splitter)
                if beamline is None:
                    beamline = beamline_source

        manufacturer = None
        model = None
        location = None

        make_string = self._lists_to_values(
            self._full_header_dict.get('_diffrn_source.make'))
        if make_string is not None:
            manufacturer, model = make_string.split('-')

        location_string = self._lists_to_values(
            self._full_header_dict.get('_diffrn_source.details'))

        if location_string is not None:
            location = location_string

        source_info = {'beamline' : beamline,
                       'facility' : facility,
                       'manufacturer' : manufacturer,
                       'model' : model,
                       'location' : location}

        return source_info


    def get_axes_info(self):
        """Return the information about the axes settings. Cif block: _axis.
        If some of the returned dictionary values is None, this notifies about
        missing information and in this case the names of axes extracted from
        the scan must be contained in the keys 'gonio_axes_found', 'det_rot_axes_found'
        and 'det_trans_axes_found'.

        Returns:
            dict: a dictionary containing the information about the axes settings
        """

        print('# Entering axes info getter')

        axes = self._full_header_dict.get('_axis.id')
        axis_type = self._full_header_dict.get('_axis.type')
        equip = self._full_header_dict.get('_axis.equipment')
        depends_on = self._full_header_dict.get('_axis.depends_on')

        vector = []
        offset = []
        # if this is from full cbf
        if axes is not None:
            for idx, _ in enumerate(axes):
                sub_vector = []
                sub_offset = []

                # possible with pycifrw but uninituitive
                # assign the vector and offset to the corresponding axis id
                # from the full header we obtain only the column with all axes
                for i in [1, 2, 3]:
                    entry = self._full_header_dict.get(f'_axis.vector[{i}]')
                    entry = entry[idx] if entry is not None else entry
                    sub_vector.append(entry)
                    entry = self._full_header_dict.get(f'_axis.offset[{i}]')
                    entry = entry[idx] if entry is not None else entry
                    sub_offset.append(entry)

                vector.append(sub_vector)
                offset.append(sub_offset)

            axes_info = {'axes' : axes,
                        'axis_type' : axis_type,
                        'equip' : equip,
                        'depends_on' : depends_on,
                        'vector' : vector,
                        'offset' : offset}

        else:
            # 'None' notifies about missing information
            axes_info = {'axes' : None}
            found_axes = self._scan_info_mini_header[self._first_scan][0].keys()
            gonio_axes = [axis for axis in found_axes if axis in
                          imgcif_creator.GONIOMETER_AXES]
            det_axes = [axis for axis in found_axes if axis in
                          imgcif_creator.DETECTOR_AXES]
            unidentified_axes = [axis for axis in found_axes if
                                 axis not in gonio_axes and axis not in det_axes]
            if len(unidentified_axes) > 0:
                print(f"The axes: {', '.join(unidentified_axes)} could not be identified \
as goniometer or detector axes.")

            gonio_stacking = \
                sorted(gonio_axes,
                       key=lambda x: imgcif_creator.GONIOMETER_AXES.index(x))
            gonio_rot_senses = ['c' for _ in gonio_stacking]

            gon_axes_senses = (gonio_stacking, gonio_rot_senses)
            axes_info['gonio_axes_found'] = gon_axes_senses

            det_trans = [axis for axis in det_axes if axis in \
                imgcif_creator.TRANS_AXES]
            det_rot = [axis for axis in det_axes if axis in \
                imgcif_creator.ROT_AXES]

            det_rot_senses = ['c' for _ in det_rot]
            det_axes_senses = (det_rot, det_rot_senses)
            axes_info['det_rot_axes_found'] = det_axes_senses
            axes_info['det_trans_axes_found'] = det_trans

        #print(axes_info)
        return axes_info


    def get_array_info(self):
        """Return the information about the array. Cif block: _array_structure_list_axis
        and _array_structure_list

        Returns:
            dict: a dictionary containing the information about the array
        """

        print('# Entering array info getter')

        # array structure list axis
        base = "_array_structure_list_axis."
        axis_id = self._full_header_dict.get(base + "axis_id")
        axis_set_id = self._full_header_dict.get(base + "axis_set_id")
        pixel_size = self._full_header_dict.get(base + "displacement_increment")

        if pixel_size is None:
            x_px = self._scan_info_mini_header[self._first_scan][1]['x_pixel_size']
            y_px = self._scan_info_mini_header[self._first_scan][1]['y_pixel_size']
            pixel_size = [x_px, y_px]

        # array structure list
        base = "_array_structure_list."
        array_id = self._full_header_dict.get(base + "array_id")
        array_index = self._full_header_dict.get(base + "index")
        array_dimension = self._full_header_dict.get(base + "dimension")

        if array_dimension is None:
            fast_dim, _ = self._get_cbf_header_values(
                self.first_mini_header, 'x-binary-size-fastest-dimension:',
                with_unit=False)
            slow_dim, _ = self._get_cbf_header_values(
                self.first_mini_header, 'x-binary-size-second-dimension:',
                with_unit=False)

            if fast_dim is not None and slow_dim is not None:
                fast_dim = int(fast_dim)
                slow_dim = int(slow_dim)
                array_dimension = [fast_dim, slow_dim]

        array_direction = self._full_header_dict.get(base + "direction")
        array_precedence = self._full_header_dict.get(base + "precedence")

        array_info = {
            'axis_id' : axis_id,
            'axis_set_id': axis_set_id,
            'pixel_size' : pixel_size,
            'array_id' : array_id,
            'array_index' : array_index,
            'array_dimension' : array_dimension,
            'array_direction' : array_direction,
            'array_precedence' : array_precedence,
        }
        print(array_info)
        return array_info


    def get_detector_info(self):
        """Return the information about the detector. Cif block: _diffrn_detector
        and _diffrn_detector_axis.

        Returns:
            dict: a dictionary containing the information about the detector
        """

        print('# Entering detector info getter')

        #TODO multiple detectors are not supportet (yet?)
        detector_id = \
            self._full_header_dict.get('_diffrn_detector.id')
        number_of_axes = \
            self._full_header_dict.get('_diffrn_detector_axis.number_of_axes')

        axis_id = self._full_header_dict.get('_diffrn_detector_axis.axis_id')
        detector_axis_id = self._full_header_dict.get('_diffrn_detector_axis.detector_id')

        detector_info = {
            'detector_id' : detector_id,
            'number_of_axes' : number_of_axes,
            'axis_id' : axis_id,
            'detector_axis_id' : detector_axis_id
        }
        return detector_info


    def get_radiation_info(self):
        """Return the information about the wavelength an type of radiation.
        Cif block: _diffrn_radiation and _diffrn_radiation_wavelength

        Returns:
           dict: a dictionary containing the information about the radiation
        """

        print('# Entering radiation info getter')

       # TODO not creating a list of wavelength id's here (yet?)
        rad_type = \
            self._full_header_dict.get('_diffrn_radiation.type')

        # get from full header
        wavelength = None
        base = '_diffrn_radiation_wavelength.'
        for identifier in ['wavelength', 'value']:
            if wavelength is None:
                wavelength = self._full_header_dict.get(base + identifier)

        # get from mini header
        # assert that it is the same wavelength in each scan?
        if wavelength is None:
            wavelength = self._scan_info_mini_header[self._first_scan][1].get('wavelength')

        return {'rad_type' : rad_type,
                'wavelength' : wavelength}


    def get_scan_settings_info(self):
        """Return the information about the scans, this is a dictionary containing
        the starting point settings of the axes and the details of each scan.

        For example for scan '08':
        {'08': ({'chi': -60.991, 'phi': 110.0, 'detector_2theta': -12.4,
        'omega': -18.679, 'distance': 40.0}, {'frames': 12, 'axis': 'omega',
        'incr': 2.0, 'time': 1800.0, 'start': -40.679, 'range': 24.0,
        'wavelength': 0.560834, 'x_pixel_size': 0.172, 'y_pixel_size': 0.172,
        'mini_header': ['# detector: pilatus100k',.... ],
        ...}

        Returns:
            dict: a dictionary containing the information about the scans
        """

        print('# Entering scan-settings info getter')

        return self._scan_info_mini_header


    def _get_scans_and_frames(self, frame_dir, stem=r".*?_"):
        """Extract scan information from minicbf or ADSC files.

        Assumptions:
        1. files are named in some form of xxxx_scanno(_)frameno.cbf
        2. frames are sequential
        3. The first frame will be scan 1 frame 1
        4. filenames are the same length
        5. "<axis>_increment" signals the increment

        Example all frames:
        {('scan name', frame number): {'filename': 'ciclohexano3_010001.cbf'}, ...}
        Example unique scans:
        {'06', '03', '07', '01', '04', '08', '02', '05'}

        Args:
            frame_dir (str): the directory where the frames are located
            stem (regexp, optional): The constant portion of the scan/frame
                naming convention. Defaults to r".*?_".

        Returns:
            tuple: the unique scan names in a set and the scan name / scan frame
                file mapping
        """

        scan_frame_regex, all_names = self._get_scan_frame_fmt(frame_dir, stem=stem)

        pattern = re.compile(scan_frame_regex)
        all_frames = {}
        # if we can't find a matched scan, we assume that there is only one called "01"
        for name in all_names:
            matched = pattern.match(name)
            if matched.groupdict().get("scan"):
                all_frames[(matched["scan"], int(matched["frame"]))] = \
                    {'filename' : name}
            else:
                all_frames[("01", int(matched["frame"]))] = {'filename' : name}

        # find the unique scans
        unique_scans = set(map(lambda x: x[0], all_frames.keys()))
        print(f"{len(unique_scans)} scan(s) found")

        return unique_scans, all_frames


    def _get_info_full_header(self, frame_dir, unique_scans, all_frames):
        """Return the information that can be found in the complete cbf file.

        Args:
            frame_dir (str): the directory containing the files with frames
            unique_scans (set): a set of unique scans
            all_frames (_type_): a dictionary containing the link between frames
                and filenames.

        Returns:
            dict: a dictionary containing the information from the complete cbf
                file per scan
        """

        scan_info = {}
        for scan in unique_scans:
            # Get information from first frame
            file_name = os.path.join(frame_dir, all_frames[(scan, 1)]['filename'])
            full_header = full_cbf.extract_full_cbf_header_information(file_name)

            scan_info[scan] = full_header

        return scan_info


    def _get_scan_info_mini_header(self, frame_dir, unique_scans, all_frames):
        """Get the scan information from the mini header.

        Args:
            frame_dir (str): the directory containing the files with frames
            unique_scans (set): a set of unique scans
            all_frames (_type_): a dictionary containing the link between frames
                and filenames.

        Raises:
            Exception: scan range does not match increment

        Returns:
            dict: a dictionary containing the scan information
        """

        scan_info = {}
        axes = imgcif_creator.ROT_AXES + imgcif_creator.TRANS_AXES
        frame_type = self._determine_frame_type(
            os.path.join(frame_dir, all_frames[list(all_frames)[0]]['filename']))

        print(f"Discovered {frame_type} files")
        print('Retrieving scan information...')

        for scan in unique_scans:

            scan_frame_map = list(filter(lambda x: x[0] == scan, all_frames.keys()))
            frames = [x[1] for x in scan_frame_map]

            # Get information for first frame
            file_name = os.path.join(frame_dir, all_frames[(scan, 1)]['filename'])
            mini_header = self._get_mini_header(file_name, frame_type)
            axes_settings, scan_ax, scan_incr, exposure, wavelength, = \
                self._get_frame_info(mini_header, frame_type, axes)
            x_pixel_size, y_pixel_size, = self._get_pixel_sizes(mini_header, frame_type)
            print(f"Identified {scan_ax} as scan axis in scan {scan}")
            start = axes_settings[scan_ax]

            # Get information for last frame
            file_name = \
                os.path.join(frame_dir, all_frames[(scan, len(frames))]['filename'])
            mini_header = self._get_mini_header(file_name, frame_type)
            axes_settings, _, _, _, _ = self._get_frame_info(mini_header, frame_type, axes)
            finish = axes_settings[scan_ax]

            # Check increment and range match
            print(f"{start} plus {scan_incr} getting to {finish}")
            if not np.isclose(start + scan_incr * (len(frames)-1), finish, atol=1e-6):
                raise Exception(
                    f"Scan range does not match increment: \
    {start} to {finish}, {len(frames)-1} steps of {scan_incr}")

            scan_details = {"frames" : len(frames),
                            "axis" : scan_ax,
                            "incr" : scan_incr,
                            "time" : exposure,
                            "start" : start,
                            # because of 0.1*137 = 13.700000000000001 we round
                            "range" : round(scan_incr * len(frames), 10),
                            "wavelength" : wavelength,
                            "x_pixel_size" : x_pixel_size,
                            "y_pixel_size" : y_pixel_size,
                            "mini_header" : mini_header
                            }
            scan_info[scan] = (axes_settings, scan_details)

        scan_info = extractor_utils.prune_scan_info(scan_info)

        return scan_info, frame_type


    def _get_scan_frame_fmt(self, frame_dir, stem=r".*?_"):
        """Deduce the scan/frame naming convention.

        Args:
            frame_dir (str): the directory containing the files with frames
            stem (regexp, optional): The constant portion of the scan/frame
                naming convention. Defaults to r".*?_".

        Returns:
            scan_frame_regex (regexp): the regular expression to identiy scans and frames
            all_names (list): a list of all filenames
        """

        file_pattern = re.compile(stem)
        all_names = []
        for _, _, files in os.walk(frame_dir):
            for filename in files:
                all_names.append(filename)

        # filter out only .cbf and .img files
        all_names = list(filter(
            lambda f_name: f_name.endswith(".cbf") or f_name.endswith(".img"),
            all_names))

        # if given a file stem filter out only the files that start with the stem/file_pattern
        all_names = list(filter(lambda f_name: file_pattern.match(f_name), all_names))
        all_names.sort()

        # Analyse number of digits between stem and extension: if less than
        # 5, no scan present the default stem matches everything until the _
        test_name = all_names[0]
        stem_len = len(file_pattern.match(test_name).group(0))
        num_digits = len(re.sub("[^0-9]", "", test_name[(stem_len-1):-4]))

        if num_digits >= 5:
            scan_frame_regex = None
            # Allow first scan not to be scan 1
            for scan in [str(i) for i in range(1, 10)]:
                regex = r"(?:" + stem + r")" +\
                    r"(?:(?P<scan>[0-9]*" + re.escape(scan) + \
                    r")(?P<sep>0|_)(?P<frame>[0-9]+1)(?P<ext>\.cbf|img))"
                # keep in mind that re.match matche only the beginning of string
                match = re.match(regex, all_names[0])

                if match:
                    scan_len = len(match.group("scan"))
                    frame_len = len(match.group("frame"))

                    # if the separator is a 0, include it
                    if match.group("sep") == "0":
                        frame_len += 1

                    scan_frame_regex = r"(?:" + stem + r")" +\
                        r"(?:(?P<scan>[0-9]{" + re.escape(str(scan_len)) + r"})" +\
                        r"_?(?P<frame>[0-9]{" + re.escape(str(frame_len)) + r"}))"

                    break
        else:
            scan_frame_regex = r"(?:" + stem + r")" + r"(?:(?P<frame>[0-9]+))"

        if scan_frame_regex is None:
            print(f"Cannot find a scan/frame naming pattern for {test_name}. \
Try to provide the constant stem of the file name using the -s option.\n")
            sys.exit()

        assert re.match(scan_frame_regex, all_names[-1]), "Regular expression for first \
    frame is not matching the last frame."

        print(f'\nFound scan/frame naming convention!')

        return scan_frame_regex, all_names


    def _determine_frame_type(self, filename):
        """Determine the type of a frame file: currently SMV (ADSC) and CBF are
        recognised.

        Args:
            filename (str): the filename for which the frame type should be
                determined

        Returns:
            str: the fileformat
        """

        with open(filename, 'rb') as file:
            # read first 512 characters/bytes as byte string
            header = file.read(512)
            # TODO ensure this! maybe its also 0x0c for the form feed character
            if b'HEADER_BYTES' in header:
                return 'SMV'
            if b'_array_data' in header:
                return 'CBF'

        return ''


    def _get_frame_info(self, mini_header, frame_type, axes):
        """Choose the method to extract frame information according to the fileformat

        Args:
            mini_header (list): the lines of the miniheader
            frame_type (str): the frame type
            axes (tuple): a tuple of axis names

        Returns:
            method: the suitable method to extract the frame info
        """

        if frame_type == "CBF":
            return self._get_frame_info_cbf(mini_header, axes)
        if frame_type == "SMV":
            return self._get_frame_info_smv(mini_header)

        return None


    def _get_mini_header(self, filename, frame_type):
        """Choose the method to extract mini header information according to the
        fileformat

        Args:
            filename (str): the filename for which the frame type should be
                determined
            frame_type (str): the type of the frames

        Returns:
            method: the suitable method to extract the mini header
        """

        if frame_type == "CBF":
            return self._get_cbf_header(filename)
        if frame_type == "SMV":
            return self._get_smv_header(filename)

        return None


    def _get_cbf_header(self, filename):
        """Return the lines of the mini header of a cbf file.

        Args:
            filename (str): the cbf filename

        Returns:
            list: a list containing the lines of the mini header
        """

        with open(filename, 'br') as file:
            cbf_header = []
            binary_info = []
            found_header = False
            within_mini_header = False
            within_binary_info = False
            for line in file:
                # select only the mini header part since otherwise e.g. comments
                # with same names could be problematic
                if b'_array_data.header_contents' in line:
                    found_header = True
                # consider that the mini header is enclosed within two lines of ';'
                elif line in (b';\n', b';\r\n', b';\r'):
                    within_mini_header = not within_mini_header
                elif b"-BINARY-FORMAT-SECTION-" in line:
                    within_binary_info = not within_binary_info

                if within_binary_info:
                    try:
                        binary_info.append(line.decode('utf-8').lower().strip('\n').strip('\r'))
                    except UnicodeDecodeError:
                        break

                if found_header and within_mini_header and line.startswith(b'#'):
                    cbf_header.append(line.decode('utf-8').lower().strip('\n').strip('\r'))

        return cbf_header + binary_info


    def _get_frame_info_cbf(self, cbf_header, axes):
        """Return any values found for provided axes. All axes converted to lowercase.
        Return also the exposure time and the wavelength and determine the scan
        axis.

        Args:
            cbf_header (list): a list of lines from the cbf mini header
            axes (tuple): the axes for which the values should be retrieved

        Raises:
            Exception: if the scan axis found does not match with an axis name

        Returns:
            ax_vals (dict): the retrieved values for the given axes
            matching_scan_ax (str): the axis indentified as scan axis that also
                matched with the given axes
            scan_ax (float): the scan axis increment
            exposure (float): the exposure time in seconds
            wavelength (float): the wavelength in Angstrom
        """

        ax_vals = \
            list(map(lambda ax:
                     (ax.lower(), self._get_cbf_header_values(cbf_header, ax)), axes))
        ax_vals = list(filter(lambda x: x[1][0] is not None, ax_vals))
        ax_vals = [self._convert_units(ax_val, 'length') for ax_val in ax_vals]

        ax_incr = list(map(lambda ax: (ax.lower(), self._get_cbf_header_values(
            cbf_header, ax + "_increment")), axes))
        ax_incr = list(filter(lambda x: x[1][0] is not None, ax_incr))
        ax_incr = [self._convert_units(incr, 'length') for incr in ax_incr]

        _, exposure = self._convert_units(('et', self._get_cbf_header_values(
            cbf_header, "exposure_time")), 'time')
        _, wavelength = self._convert_units(('wavelength', self._get_cbf_header_values(
            cbf_header, "wavelength")), 'wavelength')

        # find the first element whose increment changes
        scan_ax = next(filter(lambda x: not np.isclose(x[1], 0, atol=1e-6), ax_incr), None)

        matching_scan_ax = list(filter(lambda ax: scan_ax[0] in ax[0], ax_vals))
        if matching_scan_ax == []:
            raise Exception(
                f"Could not match the scan axis found ({scan_ax}) with an axis name.")

        matching_scan_ax = matching_scan_ax[0][0]

        # Get rid of duplicate names
        ax_vals = dict(ax_vals)

        if "distance" in  ax_vals and "detector_distance" in ax_vals:
            del ax_vals["detector_distance"]

        # Some Pilatus headers do not mention omega, just "start_angle"
        # and "angle_increment".
        if "start_angle" in ax_vals and "angle" in ax_vals:
            del ax_vals["start_angle"]

            if matching_scan_ax != "angle":   #we have an actual one
                del ax_vals["angle"]

        scan_ax, matching_scan_ax, ax_vals = self._replace_unspecified_oscillation_axis(
            cbf_header, ax_vals, matching_scan_ax, scan_ax)

        return ax_vals, matching_scan_ax, scan_ax[1], exposure, wavelength


    def _get_frame_info_smv(self, smv_header):
        
        # For a single-axis diffractometer currently

        ax_vals = [("phi", self._get_smv_header_values(smv_header, "phi")[0])]
        ax_vals.append(("trans", self._get_smv_header_values(smv_header, "distance")[0]))
        ax_incr = [("phi", self._get_smv_header_values(smv_header, "osc_range")[0])]
        ax_incr.append(("trans", 0.0))

        exposure = self._get_smv_header_values(smv_header, "time")[0]
        wavelength = self._get_smv_header_values(smv_header, "wavelength")[0]

        return dict(ax_vals), "phi", ax_incr[0][1], exposure, wavelength


    def _get_cbf_header_values(self, lines, matcher, with_unit=True, is_number=True):
        """Get the value following the string given in matcher and units if present.

        Args:
            lines (list): the list of lines from the mini header
            matcher (str): the string that should be matched in the lines
            with_unit (bool): wheter the header value has an unit at the end.
                Defauls to True.
            is_number (bool): wheter the header value is a number. Defauls to True.

        Returns:
            val (float): the value that has been matched
            units (str): the units of the value that has been matched
        """

        pattern = re.compile(re.escape(matcher) + r"[ =]+")
        matching_lines = list(filter(lambda x: pattern.search(x) is not None, lines))

        # TODO possible issues if there is more than one line matching?
        if len(matching_lines) < 1:
            return None, None

        val_unit_regex = re.escape(matcher) + r"[ =]+(?P<val>[A-Za-z0-9+-.]+)"
        if with_unit:
            val_unit_regex += r" +(?P<units>[A-Za-z.]+)"

        val_unit = [re.search(val_unit_regex, matching_line)
                    for matching_line in matching_lines]

        val = val_unit[0]["val"].strip()
        if with_unit:
            units = val_unit[0]["units"].strip()
        else:
            units = None

        if is_number:
            val = float(val)

        return val, units

    def _get_pixel_sizes(self, lines, frame_type):

        if frame_type=='CBF':
            return self._get_pixel_sizes_cbf(lines)
        else:
            return self._get_pixel_sizes_smv(lines)

    def _get_pixel_sizes_cbf(self, lines):
        """Return the pixel sized found in the given lines.

        Args:
            lines (list): a list of lines found in the mini header

        Returns:
            x_pixel (float): the x pixel size in mm
            y_pixel (float): the y pixel size in mm
        """

        matcher = 'pixel_size'
        pattern = re.compile(re.escape(matcher) + r"[ =]+")
        matching_lines = list(filter(lambda x: pattern.search(x) is not None, lines))
        if len(matching_lines) < 1:
            return None, None, None, None

        dim = r"([A-Za-z0-9+-.]+) +([A-Za-z.]+)"
        val_unit_regex = re.escape(matcher) + r'[ =]+' + dim + r' [A-Za-z] ' + dim
        val_unit = [re.search(val_unit_regex, matching_line)
                    for matching_line in matching_lines]
        val_unit = val_unit[0]
        pixel_sizes = [group.strip() for group in val_unit.groups()]

        # as it is in mm now, we round to 5 decimal places since otherwise:
        # >>> 0.000172*1000 = 0.17200000000000001
        _, x_pixel = self._convert_units(
            ('x_size', (float(pixel_sizes[0]), pixel_sizes[1])), 'length')
        _, y_pixel = self._convert_units(
            ('y_size', (float(pixel_sizes[2]), pixel_sizes[3])), 'length')

        return round(x_pixel, 5), round(y_pixel, 5)

    def _get_pixel_sizes_smv(self, lines):
        """Return the pixel size found in the given lines.

        Args:
            lines (list): a list of lines found in the mini header

        Returns:
            x_pixel (float): the x pixel size in mm
            y_pixel (float): the y pixel size in mm
        """

        matcher = 'pixel_size'
        dim = r"([0-9+-.]+)"
        pattern = re.compile(re.escape(matcher) + r"[ =]+" + dim)
        matching_lines = list(filter(lambda x: pattern.search(x) is not None, lines))
        if len(matching_lines) < 1:
            return None, None, None, None

        val_unit = [re.search(pattern, matching_line)
                    for matching_line in matching_lines]
        val_unit = val_unit[0]
        pixel_sizes = [float(group.strip()) for group in val_unit.groups()]

        # as it is in mm now, we round to 5 decimal places since otherwise:
        # >>> 0.000172*1000 = 0.17200000000000001
 
        return pixel_sizes[0], pixel_sizes[0]

    def _get_smv_header(self, filename):

        with open(filename, 'rb') as file:
            header = file.read(512)
            header = header.decode('utf-8').lower()
            smv_header = header.split("\n")
            full_length = int(self._get_smv_header_values(smv_header,"header_bytes")[0])
            print(f"Found header length {full_length}")
            file.seek(0)
            header = file.read(full_length).decode('utf-8').lower()
            smv_header = header.split("\n")

        return smv_header


    def _get_smv_header_values(self, lines, matcher):
        """
        Get the value following the string given in matcher and units if present
        """
        # TODO most likely this does not work for smv
        pattern = re.compile(r"^" + re.escape(matcher) + r"[ =]+")
        # rr = Regex("^$matcher[ =]+")
        matching_line = list(filter(lambda x: pattern.search(x) is not None, lines))
        # one_line = filter( x-> !isnothing(match(rr, x)), lines)

        if len(matching_line) != 1:
            return None, None

        matching_line = matching_line[0]

        val_regex = re.escape(matcher) + \
            r"[ =]+(?P<val>[A-Za-z0-9+-.]+)"
        val_unit = re.search(val_regex, matching_line)
        val = val_unit["val"].strip()

        # m = match(Regex("$matcher[ =]+(?<val>[A-Za-z0-9+-.]+)"), one_line)
        # val = strip(m["val"])
        #@debug "To get value" val

        return float(val), None


    def _lists_to_values(self, param):
        """If single lenght lists occur, convert them to a single value.

        Args:
            param (Any): the parameter to check

        Returns:
            Any: the parameter converted to a single entry
        """

        if isinstance(param, list) and len(param) == 1:
            return param[0]
        return param



    def _convert_units(self, ax_val, val_type):
        """Convert into units used in the imgCIF format (mm, s, Angstrom)

        Args:
            ax_val (tuple): the name, (value, unit) of the entry to convert
            val_type (str): the type of the value (to distingusish between lenghts
                and wavelengths)

        Returns:
            name (str): the name of the converted value
            val (float): the value after conversion
        """

        conversion_map = {('length', 'm') : 1e3, ('length', 'cm') : 10,
                          ('time', 'ms') : 1e-3, ('time', 'us') : 1e-6,
                          ('time', 'ns') : 1e-9, ('wavelength', 'nm') : 1e-1}

        name, (val, unit) = ax_val
        if (val_type, unit) in conversion_map.keys():
            val = val * conversion_map[(val_type, unit)]

        return name, val


    def _replace_unspecified_oscillation_axis(self, cbf_header, ax_vals,
                                              matching_scan_ax, scan_ax):
        """Replace a generic name with a more useful one if the oscillation axis is
        specified e.g. angle -> omega

        Args:
            cbf_header (list): a list of lines from the cbf mini header
            ax_vals (dict): the retrieved values for the given axes
            matching_scan_ax (str): the axis indentified as scan axis that also
                matched with the given axes
            scan_ax (float): the scan axis increment

        Returns:
            ax_vals (dict): same as input with possible name replacements
            matching_scan_ax (str): same as input with possible name replacements
            scan_ax (float): same as input with possible name replacements
        """

        osc_axis = self._get_cbf_header_values(cbf_header, 'oscillation_axis',
                                               is_number=False, with_unit=False)
        replace = False
        if osc_axis[0] is not None:
            if matching_scan_ax in imgcif_creator.GONIOMETER_AXES:
                if matching_scan_ax == 'angle':
                    replace = True
            else:
                replace = True

        if replace:
            ax_vals[osc_axis[0]] = ax_vals[scan_ax[0]]
            del ax_vals[scan_ax[0]]
            scan_ax = (osc_axis[0], scan_ax[1])
            matching_scan_ax = osc_axis[0]

        return scan_ax, matching_scan_ax, ax_vals
