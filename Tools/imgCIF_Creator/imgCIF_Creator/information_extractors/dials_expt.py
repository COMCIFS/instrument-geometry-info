"""This module defines an extractor class that allows to extract information
from an expt file created with DIALS from various original input.
"""

import json
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

    def __init__(self, filename) -> None:
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
        print(self._raw_dict)

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
