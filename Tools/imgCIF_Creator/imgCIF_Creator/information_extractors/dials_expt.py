"""This module defines an extractor class that allows to extract information
from an expt file created with DIALS from various original input.
"""

from inspect import getsourcefile
import json
import os
import re
import sys
import yaml
import numpy as np
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
                be extracted
        """

        self._raw_dict = self._ingest_json(filename)
        print(self._raw_dict, '\n\n')
        self._resources_path = os.path.abspath(getsourcefile(lambda: 0)).replace(
            'information_extractors/dials_expt.py', 'resources/')

        with open(f"{self._resources_path}user_input.yaml", 'r') as stream:
            try:
                input_options = yaml.safe_load(stream)
                self._facility_options = input_options['facility']['options']
            except yaml.YAMLError as error:
                print(error)


    def get_source_info(self):
        """Return the information about the facility and beamline or the instrument,
        model and location. Cif block: _diffrn_source

        Returns:
            dict: a dictionary containing the information about the source
        """

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


    def get_axes_info(self):
        """Return the information about the axes settings. Cif block: _axis

        Returns:
            dict: a dictionary containing the information about the axes settings
        """

        pass

    def get_array_info(self):
        """Return the information about the array. Cif block: _array_structure_list_axis
        and _array_structure_list

        Returns:
            dict: a dictionary containing the information about the array
        """

        pass

    def get_detector_info(self):
        """Return the information about the detector. Cif block: _diffrn_detector
        and _diffrn_detector_axis.

        Returns:
            dict: a dictionary containing the information about the detector
        """

        pass

    def get_radiation_info(self):
        """Return the information about the wavelength an type of radiation.
        Cif block: _diffrn_radiation and _diffrn_radiation_wavelength

        Returns:
           dict: a dictionary containing the information about the radiation
        """

        pass

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

        pass

    def get_misc_info(self):
        """Return the information that was found about the doi and the array
        intensities overload.

        Returns:
            dict: a dictionary containing the doi and the array intensities overload
        """

        pass

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
