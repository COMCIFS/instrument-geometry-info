"""Functionality to create the actual imgCIF file with the collected information.
"""

import re
import os
import importlib
from imgCIF_Creator.command_line_interfaces import parser
from . import block_generators

# Configuration information
# the order reflects the stacking
# GONIOMETER_BASE = ("omega", "angle", "two_theta")
GONIOMETER_AXES = ("phi", "kappa", "chi", "omega", "angle", "two_theta")
# GONIOMETER_AXES = ("chi", "phi", "two_theta", "omega", "angle", "start_angle",
#                    "kappa")

# DETECTOR_TRANS = ("detector_distance", "dx", "trans", "distance")
DETECTOR_AXES = ("detector_2theta", "detector_distance", "dx", "trans", "distance")


ROT_AXES = ("chi", "phi", "detector_2theta", "two_theta", "omega", "angle",
            "start_angle", "kappa")
TRANS_AXES = ("detector_distance", "dx", "trans", "distance")
ALWAYS_AXES = ("distance", "two_theta", "detector_2theta")
DETECTOR_ARRAY_AXES = ("detx", "dety")


class ImgCIFCreator:
    """See documentation of the __init__ method.
    """

    def __init__(self, filename, filetype, stem) -> None:
        """Initialize the imgCIFCreator and dynamically load the appropriate
        extractor module.

        Args:
            filename (str): The filename or directory where the data is located.
            filetype (str): The filetype (smv, cbf or h5)
            stem (str): constant portion of the filenames to determine the scan
                frame naming convention.
        """

        if filetype in ['smv', 'cbf']:
            extractor_module = importlib.import_module(
                'imgCIF_Creator.information_extractors.cbf_smv')
        elif filetype == 'h5':
            extractor_module = importlib.import_module(
                'imgCIF_Creator.information_extractors.hdf5_nxmx')

        self.extractor = extractor_module.Extractor(filename, stem)
        self.cmd_parser = parser.CommandLineParser()
        self.generators = block_generators.ImgCIFEntryGenerators()


    def create_imgcif(self, cif_block, external_url, prepend_dir, filename, filetype):
        """Add the required information to a cif_block and request the missing
        information from the user.

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): A cif block created with
                the pycifrw package to which the information is added.
            external_url (str): An external url of the files e.g. a zeondo url
            prepend_dir (str): If the directory name is included as part of the archive
                path name this is the prepended directory name.
            filename (str): The filename or directory where the data is located.
            filetype (str): The filetype (smv, cbf or h5)
        """

        # _diffrn_source block
        source_info = self.extractor.get_source_info()
        source_info = self.check_source_completeness(source_info)

        misc_info = self.extractor.get_misc_info()
        misc_info = self.check_misc_completeness(misc_info)

        # self.generate _diffrn_wavelength block
        radiation_info = self.extractor.get_radiation_info()
        radiation_info = self.check_radiation_completeness(radiation_info)

        # # describe _array_structure_list_axis and _array_structure_list
        array_info = self.extractor.get_array_info()
        array_info = self.check_array_completeness(array_info)

        scan_setting_info = self.extractor.get_scan_settings_info()
        # TODO this is not checking anything right now
        scan_setting_info = self.check_scan_settings_completeness(scan_setting_info)
        scan_list = self.generate_scan_list(scan_setting_info)

        # describe _axis block
        axes_info = self.extractor.get_axes_info()
        axes_info = self.check_axes_completeness(
            axes_info, array_info, scan_setting_info)

        # describe _diffrn_detector and _diffrn_detector_axis
        # this correlates with the detector axes in generate axes!
        detector_info = self.extractor.get_detector_info()
        detector_info = self.check_detector_completeness(detector_info, axes_info)

        archive, external_url = self.check_external_url(external_url, filename)


        # now generate the cif block
        # _diffrn_source block
        self.generators.generate_source(cif_block, source_info)
        self.generators.generate_misc(cif_block, misc_info)
        # self.generate _diffrn_wavelength block
        self.generators.generate_radiation(cif_block, radiation_info)
        # describe _axis block
        self.generators.generate_axes(cif_block, axes_info)
        # # describe _array_structure_list_axis and _array_structure_list
        self.generators.generate_array(cif_block, array_info)
        # describe _diffrn_detector and _diffrn_detector_axis
        self.generators.generate_detector(cif_block, detector_info)
        # self.generate _diffrn_scan_axis block
        self.generators.generate_scan_settings(cif_block, scan_setting_info)
        # self.generate _diffrn_scan block
        self.generators.generate_scan_info(cif_block, scan_list)
        # self.generate _diffrn_scan_frame block
        self.generators.generate_step_info(cif_block, scan_setting_info, scan_list)
        # self.generate _diffrn_data_frame block
        self.generators.generate_data_frame_info(cif_block, scan_list)
        # self.generate _array_data block
        self.generators.generate_ids(cif_block, scan_list)
        # self.generate _array_data_external_data
        self.generators.generate_external_ids(
            cif_block, external_url, self.extractor.all_frames,
            scan_list, archive, prepend_dir, filetype)


    def check_misc_completeness(self, misc_info):
        """Check if the misc information is complete and request input
        if not.

        Args:
            misc_info (dict): Some misc information that is needed.

        Returns:
            dict: the information completed
        """

        if self.param_is_none(misc_info['doi']):
            misc_info['doi'] = self.cmd_parser.request_input('doi')

        if self.param_is_none(misc_info['temperature']):
            misc_info['temperature'] = self.cmd_parser.request_input('temperature')

        return self.lists_to_values(misc_info)


    def check_source_completeness(self, source_info):
        """Check if the source information is complete and request input
        if not.
        Args:
            source_info (dict): information about the source

        Returns:
            dict: the information completed
        """

        layout = ''
        if not any(source_info.values()):
            layout = self.cmd_parser.request_input('layout')

        if layout.lower() in ['beamline', 'b'] or \
            (source_info.get('beamline') is not None) or \
            (source_info.get('facility') is not None):
            required_info = ['facility', 'beamline']
            print('\nCreating a imgCIF file for a beamline.')

        if layout.lower() in ['laboratory', 'l'] or \
            (source_info.get('manufacturer') is not None) or \
            (source_info.get('model') is not None) or \
            (source_info.get('location') is not None):
            required_info = ['manufacturer', 'model', 'location']
            print('\nCreating a imgCIF file for a laboratory setup.')


        for info in required_info:
            if source_info.get(info) is None:
                source_info[info] = self.cmd_parser.request_input(info)
            else:
                print(f'\nFound the following information about the {info}: \
{source_info[info]}')
        # print('')

        # base = "_diffrn_source."
        # if "Beamline name" in raw_info or "Facility name" in raw_info:
        #     cif_block[base + "beamline"] = [raw_info["Beamline name"]]
        #     cif_block[base + "facility"] = [raw_info["Facility name"]]
        # else:
        #     cif_block[base + "make"] = [raw_info["Name of manufacturer"] + "-" + \
        #         raw_info["Model"]]
        #     if "Location" in raw_info:
        #         cif_block[base + "details"] = [f"Located at {raw_info['Location']}"]

        return self.lists_to_values(source_info)


    def check_axes_completeness(self, axes_info, array_info, scan_settings_info):
        """Check if the axes information is complete and request input if not.

        Args:
            axes_info (dict): information about the axes
            array_info (dict): information about the data array
            scan_settings_info (dict): information about the scans

        Returns:
            dict: the information completed
        """

        # print('axinf', axes_info)
        lengths = [len(values) for values in axes_info.values() if values is not None]
        has_same_len = all([length == lengths[0] for length in lengths])

        missing_information = False
        for value in axes_info.values():
            if self.param_is_none(value):
                missing_information = True

        if missing_information or not has_same_len:

            gon_axes, principal_sense = self._complete_goniometer_axes(axes_info)
            det_axes = self._complete_detector_axes(axes_info, principal_sense,
                                                    array_info, scan_settings_info)

            for key in gon_axes:
                gon_axes[key] += det_axes[key]

            return gon_axes

        # print('gox', gon_axes)
        # print('dx', det_axes)
        return axes_info


    def check_array_completeness(self, array_info):
        """Check if the array information is complete and request input
        if not.

        Args:
            array_info (dict): information about the data array

        Returns:
            dict: the completed information
        """

        # TODO check hardcoded stuff
        array_structure_labels = ['axis_id', 'axis_set_id', 'pixel_size']
        if any([self.param_is_none(array_info[label]) for label in array_structure_labels]):

            array_info["axis_id"] = ["detx", "dety"]
            array_info["axis_set_id"] = [1, 2]

            if self.param_is_none(array_info['pixel_size']):
                array_info['pixel_size'] = self.cmd_parser.request_input('pixel_size')

        array_structure_list_labels = ['array_id', 'array_index', 'array_dimension',
                                       'array_direction', 'array_precedence']
        if any([self.param_is_none(array_info[label]) for label in array_structure_list_labels]):

            array_info["array_id"] = [1, 1]
            array_info["array_index"] = [1, 2]
            array_info["axis_set_id"] = [1, 2]

            if self.param_is_none(array_info['array_dimension']):
                array_info['array_dimension'] = \
                    self.cmd_parser.request_input('array_dimension').replace(' ', '').split(',')

            array_info["array_direction"] = ["increasing", "increasing"]

            if self.param_is_none(array_info['array_precedence']):
                fast_direction = self.cmd_parser.request_input('fast_direction')
                if fast_direction in ["horizontal", 'h']:
                    array_info['array_precedence'] = [1, 2]
                else:
                    array_info['array_precedence'] = [2, 1]

        return array_info


    def check_detector_completeness(self, detector_info, axes_info):
        """Check if the detector information is complete and request input
        if not.

        Args:
            detector_info (dict): information about the detector
            axes_info (dict): information about the axes

        Returns:
            dict: the information completed
        """

        # TODO does not include multiple detectors yet

        if self.param_is_none(detector_info["detector_id"]):
            detector_info["detector_id"] = ['det1']

        detector_axes_labels = ['number_of_axes', 'axis_id']

        if any([self.param_is_none(detector_info[label]) for label in detector_axes_labels]):
            det_axes = []
            for idx, axis in enumerate(axes_info['axes']):
                # skip detx, dety
                if axis in DETECTOR_ARRAY_AXES:
                    continue
                if axes_info['equip'][idx] == 'detector' \
                    and axes_info['axis_type'][idx] == 'translation':
                    det_axes.append(axis)

            if len(det_axes) < 1:
                det_axes = self.cmd_parser.request_input('detector_axes').split(',')
                det_axes = [axis.strip() for axis in det_axes]
                det_axes = [axis for axis in det_axes if axis != '']

            detector_info["number_of_axes"] = [len(det_axes)]
            detector_info["axis_id"] = det_axes

        #TODO it's not ensured that this is always a list...
        detector_info["detector_axis_id"] = \
            detector_info["detector_id"] * len(detector_info["axis_id"])

        return detector_info


    def check_radiation_completeness(self, radiation_info):
        """Check if the wavelength information is complete and request input
        if not.

        Args:
            radiation_info (dict): the information about the radiation

        Returns:
            dict: the informatio completed
        """

        if self.param_is_none(radiation_info['rad_type']):
            radiation_info['rad_type'] = \
                self.cmd_parser.request_input('rad_type')
            if radiation_info['rad_type'] == '':
                radiation_info['rad_type'] = 'x-ray'

        if self.param_is_none(radiation_info['wavelength']):
            radiation_info['wavelength'] = \
                self.cmd_parser.request_input('wavelength')

        return self.lists_to_values(radiation_info)


    def check_scan_settings_completeness(self, scan_settings_info):
        """Check if the scan information is complete and request input
        if not.

        Args:
            scan_settings_info (dict): the scan setting information where the
                key is the scan and the informaton is stored in a tuple containing
                dictionaries with information about the axes and the scan details

        Returns:
            dict: the information completed
        """

        # does not need to ask for wl since this is done in radiation_info
        # same for pixel size, which is done in array_info
        # the other parameters are scan dependent? doesn't make sense to request
        # that from the user?
        # TODO

        return scan_settings_info


    def generate_scan_list(self, scan_setting_info):
        """Generate a list contaning tuples with the scan name and the number of
        frames, e.g. [('01', 325)]

        Args:
            scan_settings_info (dict): the scan setting information where the
                key is the scan and the informaton is stored in a tuple containing
                dictionaries with information about the axes and the scan details

        Returns:
            list: a list consiting of tuples with the scan name and the number of
        frames
        """
        # something like scan_list [('01', 325)]
        # Create scan list of (scanid, frame_no) where
        # frame_no is just the number of frames

        scans = sorted(scan_setting_info)
        slist = [(s, scan_setting_info[s][1]["frames"]) for s in scans]

        return slist


    def param_is_none(self, param):
        """Check if the parameter is None or if the string content is 'none'.
        For lists the result is True if already one entry is None or 'none'.

        Args:
            param (list, int, str): the parameter which shall be checked

        Returns:
            bool: True if the parameters is identified as None else False
        """

        if param is None:
            return True
        if isinstance(param, str):
            return param.lower() == 'none'
        if isinstance(param, list):
            is_none = []
            for entry in param:
                if entry is None:
                    is_none.append(True)
                elif isinstance(entry, str):
                    is_none.append(entry.lower() == 'none')
                else:
                    is_none.append(False)

            return any(is_none)

        return False


    def lists_to_values(self, param_dict):
        """Sometimes values parsed from full cbf files are single lenght lists
        which are converted into the value only with this method.

        Args:
            param_dict (dict): the dictionary containing the information

        Returns:
            dict: the same dict with single lenght lists replaced
        """

        for key, value in param_dict.items():
            if isinstance(value, list) and (len(value) == 1):
                param_dict[key] = value[0]
                # print('set', value, 'to', param_dict[key])

        return param_dict


    def check_external_url(self, external_url, filename):
        """Get the archive type of the provided external url or return the default
        filename/path as external url if no external url was provided.

        Args:
            external_url (str): the external url wich possibly points to an archive
                format
            filename (str): The filename or directory where the data is located.

        Returns:
            tuple: the archive format str and the external url
        """

        archive = None

        if external_url == '':
            external_url = self.cmd_parser.request_input('external_url')

        if external_url == 'force local':
            filename = filename[1:] if filename.startswith(os.sep) else filename
            external_url = f"file:{os.sep}{os.sep}" + filename

        archives = {"TGZ" : r"(\.tgz)|(\.tar.gz)\Z",
                    "TBZ" : r"(\.tbz)|(\.tar\.bz2)\Z",
                    "ZIP" : r"(\.zip)\Z"}

        for archive_type, regex in archives.items():
            searched = re.search(regex, external_url)
            if bool(searched) and searched.group(0) != '':
                return archive_type, external_url

        return archive, external_url


    def _change_axes(self, axes_files, parser_label):
        """Change the ordering and rotation senses of axes and add additional axes.

        Args:
            axes_files (list): the axes that were found in the files
            parser_label (str): the label that identifies which type of axes the
                parser must request

        Returns:
            axes_parsed (list): the list of parsed axes
            senses_parsed (list): the list of parsed senses
        """

        missing_axes = True
        while missing_axes:

            axes_senses = self.cmd_parser.request_input(parser_label)
            if parser_label == 'change_det_trans_axes':
                axes_parsed = [sub.strip() for sub in axes_senses.split(',')]
                senses_parsed = None
            else:
                axes_parsed, senses_parsed = \
                    self.cmd_parser.parse_axis_string(axes_senses)

            # no duplicates allowed
            if not set(axes_files).issubset(axes_parsed):
                print(f" ==> The axes found in the files ({', '.join(axes_files)}) \
are no subset of ({', '.join(axes_parsed)})! Please try again.")
                missing_axes = True
                del self.cmd_parser.parsed[parser_label]
            else:
                missing_axes = False
                return axes_parsed, senses_parsed


    def _complete_goniometer_axes(self, axes_info):
        """Use the information found in the files and construct the complete
        goniometer axes description. Ask for missing information. If no axes are
        found, the same information is requested, but no axes are predefined.

        Args:
            axes_info (dict): a dictionary that should contain the goniometer
                axes (e.g. 'phi, c, omega, c') under the key 'gonio_axes_found'
        Returns:
            gon_axes (dict): a dictionary containing the information about the
                settings of the goniometer
            principal_sense (str): the sense of the principal axis
        """

        print('\nSome information about the goniometer is missing, please enter \
the missing information. Answer the goniometer questions for all axes in zero position.')

        goniometer_axes_in_file = axes_info.get('gonio_axes_found') \
            if axes_info.get('gonio_axes_found') is not None else ([], [])

        axes_files, senses_files = goniometer_axes_in_file
        message = ', '.join([f'{ax} ({senses_files[idx]})' \
        for idx, ax in enumerate(axes_files)])
        print(f"\nSome goniometer rotation axes and assumed rotations were found. \
Rotations are, when looking from the crystal in the direction of the goniometer, \
c=clockwise or a=anticlockwise. The output order reflects the stacking from \
closest to the crystal to furthest from the crystal. The axes are: \n ==> {message}")

        # offer possibility to change ordering and rotation senses, not names
        keep_axes = self.cmd_parser.request_input('keep_axes')
        if keep_axes in ['no', 'n']:
            goniometer_axes = self._change_axes(
                axes_files, 'change_goniometer_axes')
        else:
            goniometer_axes = (axes_files, senses_files)

        new_regex_stem = r'(' + r'|'.join(goniometer_axes[0]) + r')'
        # make case insensitive
        new_regex = r'(?i)(' + new_regex_stem + r'((\s|,)(\s)*\d{1,3}){1,2}' + r')\Z'
        self.cmd_parser.validation_regex['kappa_axis'] = new_regex
        kappa_axis = self.cmd_parser.request_input('kappa_axis')

        new_regex = r'(?i)(' + new_regex_stem + r'((\s|,)(\s)*\d{1,3})' + r')\Z'
        self.cmd_parser.validation_regex['chi_axis'] = new_regex
        chi_axis = self.cmd_parser.request_input('chi_axis')

        gon_axes = self.cmd_parser.make_goniometer_axes(
            goniometer_axes, kappa_axis, chi_axis)

        principal_sense = goniometer_axes[1][-1]

        return gon_axes, principal_sense



    def _complete_detector_axes(self, axes_info, principal_sense, array_info,
                                scan_settings_info):
        """Use the information found in the files and construct the complete
        detector axes description. Ask for missing information. If no axes are
        found, the same information is requested, but no axes are predefined.

        Args:
            axes_info (dict): a dictionary that should contain the detector
                axes under the key 'det_trans_axes_found' and 'det_rot_axes_found'
            principal_sense (str): the rotation sense of the principal axis
            array_info (dict): information about the data array
            scan_settings_info (dict): information about the scans
        """

        print('\nSome information about the detector is missing, please enter \
the missing information. Answer the following questions assuming \
all detector positioning axes are at their home positions. This does currently \
not work for more than one detector, or non-rectangular detectors.')

        principal_angle = self.cmd_parser.request_input('principal_angle')
        image_orientation = self.cmd_parser.request_input('image_orientation')

        det_trans_axes_in_file = axes_info.get('det_trans_axes_found') \
            if axes_info.get('det_trans_axes_found') is not None else []

        axes_files, senses_files = det_trans_axes_in_file, None

        print(f"\nSome detector translation axes were found. The output \
order reflects the stacking from closest to the crystal to furthest from the \
crystal: The axes are: \n ==> {', '.join(axes_files)}")

        del self.cmd_parser.parsed['keep_axes']
        keep_axes = self.cmd_parser.request_input('keep_axes')

        if keep_axes in ['no', 'n']:
            det_trans_axes, _ = self._change_axes(
                axes_files, 'change_det_trans_axes')
        else:
            det_trans_axes = axes_files

        det_rot_axes_in_file = axes_info.get('det_rot_axes_found') \
            if axes_info.get('det_rot_axes_found') is not None else ([], [])

        axes_files, senses_files = det_rot_axes_in_file

        message = ', '.join([f'{ax} ({senses_files[idx]})' \
                                for idx, ax in enumerate(axes_files)])

        print(f"\nSome detector rotation axes and assumed rotations were found. \
Rotations are when looking from above c=clockwise or a=anticlockwise. The output \
order reflects the stacking from closest to the crystal to furthest from the \
crystal. The axes are: \n ==> {message}")

        del self.cmd_parser.parsed['keep_axes']
        keep_axes = self.cmd_parser.request_input('keep_axes')

        if keep_axes in ['no', 'n']:
            det_rot_axes = self._change_axes(
                axes_files, 'change_det_rot_axes')
        else:
            det_rot_axes = (axes_files, senses_files)

        det_axes = self.cmd_parser.make_detector_axes(
            det_trans_axes, det_rot_axes,
            principal_sense, principal_angle, image_orientation,
            # two_theta_sense,
            array_info, scan_settings_info)

        return det_axes
