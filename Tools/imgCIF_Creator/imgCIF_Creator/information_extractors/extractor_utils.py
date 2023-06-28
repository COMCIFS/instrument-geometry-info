"""This module defines an untility functions which can be used in different extractor
classes.
"""

import numpy as np
from copy import deepcopy
from imgCIF_Creator.output_creator import imgcif_creator


def prune_scan_info(scan_info, prune_always_axes=False):
    """Remove reference to any axes that do not change position and are
    essentially zero, but are not in `always_axes`.

    Args:
        scan_info (dict): a dictionary containing the scan information
        prune_always_axes (bool): whether to also prune the always axes - this
            is useful for the scan information. defaults to False.

    Returns:
        scan_info (dict): a dictionary containing the relevant scan information
    """

    # if we want to remove always axes that are zero from the scan list it needs
    # to be copied
    scan_info = deepcopy(scan_info)
    # get the scan axes and the details from the first scan
    first_axes_settings, details = scan_info[list(scan_info.keys())[0]]
    scan_axis = details["axis"]
    keep_this = [scan_axis]
    for axis, inital_val in first_axes_settings.items():
        for axes_settings, _ in scan_info.values():
            # keep axes which change their values in one of the scans
            if axes_settings[axis] != inital_val:
                keep_this.append(axis)
                break

    delete_later = []
    for axis, inital_val in first_axes_settings.items():
        condition = axis not in keep_this and np.isclose(inital_val, 0, atol=0.001)
        if not prune_always_axes:
            condition = condition and axis not in imgcif_creator.ALWAYS_AXES
        if inital_val == -9999:
            condition = True

        if condition:
            for scan in scan_info:
                delete_later.append((scan, axis))

    for scan, axis in delete_later:
        del scan_info[scan][0][axis]

    return scan_info


def gen_dict_extract(query_key, input_dict):
    """Recursive function to retrieve values of all keys matching a query
       in a nested dictionary with possible lists of sub-dictionaries.
       From: https://stackoverflow.com/questions/9807634/
       find-all-occurrences-of-a-key-in-nested-dictionaries-and-lists
    """
    if hasattr(input_dict,'items'):
        for _key, _item in input_dict.items():
            if _key == query_key:
                yield _item
            if isinstance(_item, dict):
                for result in gen_dict_extract(query_key, _item):
                    yield result
            elif isinstance(_item, list):
                for _sub_dict in _item:
                    for result in gen_dict_extract(query_key, _sub_dict):
                        yield result


def name_contained(input_dict, query_key, known_options):
    """Check strings at all matching keys in a given input metadata dictionary
    against corresponding options from known values (names) of that info type.
    Example: presence of a valid facility name in the DIALS dictionary, in the
    string value belonging to key 'identifier'

    Args:
        input_dict (dict): a dictionary containing all available input metadata
        query_key (string): a key known to possibly contain the sought info
        known_options (list): a list of strings representing valid names

    Returns:
        option (string): the matching option for the sought info type 
    """

    info_list = list(gen_dict_extract(query_key, input_dict))

    for item in info_list:
        for option in known_options:
            if option in item:
                return option

    return None
