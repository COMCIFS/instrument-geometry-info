"""Functionality to create the loops and entries in the imgCIF file.
"""
import os
import re
from . import imgcif_creator


class ImgCIFEntryGenerators():

    """See the documentation of the __init__ method
    """

    def __init__(self) -> None:
        """This class provides methods to generate the entries in the imgCIF with
        the extracted information.
        """

    def generate_misc(self, cif_block, misc_info):
        """Generate the cif_block entries for the misc information.

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            misc_info (dict): the misc information
        """

        if misc_info.get('doi') is not None:
            cif_block['_database.dataset_doi'] = misc_info['doi']

        cif_block['_diffrn.ambient_temperature'] = misc_info['temperature']
        if misc_info.get('overload') is not None:
            cif_block['_array_intensities.overload'] = misc_info['overload']


    def generate_radiation(self, cif_block, radiation_info):
        """Generate the cif_block entries for the radiation information.

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            radiation_info (dict): the information about the radiation
        """

        if radiation_info['rad_type'] is not '':
            cif_block["_diffrn_radiation.type"] = radiation_info['rad_type']

        base = "_diffrn_radiation_wavelength"
        cif_block[base + ".id"] = [1]
        cif_block[base + ".value"] = \
            [radiation_info['wavelength']]
        cif_block.CreateLoop([base + '.id', base + '.value'])


    def generate_scan_settings(self, cif_block, scan_info):
        """Generate the cif_block entries for the scan settings information.

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            scan_info (dict): the information about the scan
        """

        base = "_diffrn_scan_axis"
        entries = {
            base + '.scan_id' : [],
            base + '.axis_id': [],
            base + '.displacement_start' : [],
            base + '.displacement_increment' : [],
            base + '.displacement_range' : [],
            base + '.angle_start' : [],
            base + '.angle_increment' : [],
            base + '.angle_range' :[],
        }

        for scan in sorted(scan_info):
            axes, dets = scan_info[scan]
            for axis, val in axes.items():
                step, scan_range = 0, 0
                if axis == dets["axis"]:
                    step = dets["incr"]
                    scan_range = dets["range"]
                    val = dets["start"]

                settings = [val, step, scan_range]
                empty_settings = ['.', '.', '.']

                if axis in imgcif_creator.TRANS_AXES:
                    settings = settings + empty_settings
                else:
                    settings = empty_settings + settings

                entries[base + '.scan_id'].append(f"SCAN{scan}")
                entries[base + '.axis_id'].append(axis)
                entries[base + '.displacement_start'].append(settings[0])
                entries[base + '.displacement_increment'].append(settings[1])
                entries[base + '.displacement_range'].append(settings[2])
                entries[base + '.angle_start'].append(settings[3])
                entries[base + '.angle_increment'].append(settings[4])
                entries[base + '.angle_range'].append(settings[5])

        for name, value in entries.items():
            cif_block[name] = value

        cif_block.CreateLoop(list(entries.keys()))


    def generate_scan_info(self, cif_block, scan_list):
        """Generate the cif_block entries for the scan information.
        Fill in the scan information. We number the frames from
        the start

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            scan_list (list): a list consiting of tuples with the scan name and the number of
                frames
        """

        base = '_diffrn_scan'
        entries = {
            base + ".id" : [],
            base + ".frame_id_start" : [],
            base + ".frame_id_end" : [],
            base + ".frames" : [],
            }

        start_frame = 1
        for scan, frame in scan_list:
            end_frame = start_frame + frame - 1
            entries[base + ".id"].append(f"SCAN{scan}")
            entries[base + ".frame_id_start"].append(f"frm{start_frame}")
            entries[base + ".frame_id_end"].append(f"frm{end_frame}")
            entries[base + ".frames"].append(frame)

            start_frame = end_frame + 1

        for name, value in entries.items():
            cif_block[name] = value

        cif_block.CreateLoop(list(entries.keys()))


    def generate_ids(self, cif_block, scan_list):
        """Generate the cif_block entries for the ids.

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            scan_list (list): a list consiting of tuples with the scan name and the number of
                frames
        """
        # Array_id is just IMAGE (a single detector module). The
        # binary_id is incremented with frame, and all of them
        # are located externally so external_id is also incremented
        # together with binary_id.

        base = '_array_data'
        entries = {
            base + ".array_id" : [],
            base + ".binary_id" : [],
            base + ".external_data_id" : [],
            }

        counter = 0
        for _, frames in scan_list:
            for _ in range(1, frames + 1):
                counter += 1
                entries[base + ".array_id"].append("IMAGE01")
                entries[base + ".binary_id"].append(counter)
                entries[base + ".external_data_id"].append(f'ext{counter}')

        for name, value in entries.items():
            cif_block[name] = value

        cif_block.CreateLoop(list(entries.keys()))


    def generate_external_ids(self, cif_block, external_url, all_frames, scan_list,
                              arch, prepend_dir, file_format):
        """Generate the cif_block entries for the external ids. `external_url` is
        the location of a single archive file. The individual files
        on the local storage are assumed to be at the same locations relative to
        this top-level directory.

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            external_url (str): the location of a single archive file
            all_frames (dict): a dictionary with tuples of (scan, frame) as keys
                and the filenames as values
            scan_list (list): a list consisting of tuples with the scan name and
                the number of frames
            arch (str): the archive format of the external url
            prepend_dir (str): the directory that is prepended to the path
            file_format (str): the file format (cbf, smv, h5)
        """

        base = '_array_data_external_data'
        entries = {
            base + ".id" : [],
            base + ".format" : [],
            base + ".uri" : [],
            }

        if file_format == 'h5':
            entries[base + ".path"] = []
            entries[base + ".frame"] = []

        if arch is not None:
            entries[base + ".archive_format"] = []
            entries[base + ".archive_path"] = []

        counter = 0
        protocols = ["file:", "rsync:"]
        for scan, frames in scan_list:
            for frame in range(1, frames + 1):
                counter += 1
                frame_name = f"{all_frames[(scan, frame)]['filename']}"

                entries[base + ".id"].append(f"ext{counter}")
                file_format = 'HDF5' if file_format == 'h5' else file_format
                entries[base + ".format"].append(file_format.upper())
                if any([external_url.startswith(prot) for prot in protocols]) or\
                    file_format == 'HDF5':
                    if file_format == 'HDF5':
                        external_url = external_url.strip(external_url.split('/')[-1])
                    separator = '' if external_url.endswith(os.sep) else os.sep
                    local_url = external_url + separator + frame_name
                    entries[base + ".uri"].append(local_url)
                else:
                    entries[base + ".uri"].append(external_url)

                # TODO path and frame only for hdf5? rspectively containerized images?
                if file_format in ('h5', 'HDF5'):
                    entries[base + ".path"].append(all_frames[(scan, frame)]['path'])
                    entries[base + ".frame"].append(all_frames[(scan, frame)]['frame'])
                # A too-clever-by-half way of optionally live constructing a URL
                # TODO what is the archive path actually
                if arch is not None:
                    entries[base + ".archive_format"].append(arch)
                    separator = '' if external_url.endswith(os.sep) else os.sep
                    entries[base + ".archive_path"].append(
                        prepend_dir + separator + frame_name)

        for name, value in entries.items():
            cif_block[name] = value

        cif_block.CreateLoop(list(entries.keys()))


    def generate_step_info(self, cif_block, scan_setting_info, scan_list):
        """Generate the cif_block entries for the step information.
        Fill in information about steps

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            scan_settings_info (dict): the scan setting information where the
                key is the scan and the informaton is stored in a tuple containing
                dictionaries with information about the axes and the scan details
            scan_list (list): a list consiting of tuples with the scan name and the number of
                frames
        """

        base = '_diffrn_scan_frame'
        entries = {
            base + ".frame_id" : [],
            base + ".scan_id" : [],
            base + ".frame_number" : [],
            base + ".integration_time" : [],
            }

        counter = 0
        for scan, frames in scan_list:
            for frame_number in range(1, frames + 1):
                counter += 1
                entries[base + ".frame_id"].append(f"frm{counter}")
                entries[base + ".scan_id"].append(f"SCAN{scan}")
                entries[base + ".frame_number"].append(frame_number)
                entries[base + ".integration_time"]\
                    .append(scan_setting_info[scan][1]['time'])

        for name, value in entries.items():
            cif_block[name] = value

        cif_block.CreateLoop(list(entries.keys()))


    def generate_source(self, cif_block, source_info):
        """Generate the cif_block entries for the source information.

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            source_info (dict): information about the source
        """

        regex = r"[^A-Za-z0-9_]"
        base = "_diffrn_source."
        if source_info.get("beamline") is not None or\
             source_info.get("facility") is not None:
            cif_block[base + "beamline"] = source_info["beamline"]
            cif_block[base + "facility"] = source_info["facility"]
            audit_id_1 = re.sub(regex, '_', source_info["beamline"])
            audit_id_2 = re.sub(regex, '_', source_info["facility"])
        else:
            cif_block[base + "make"] = source_info["manufacturer"] + "-" + \
                source_info["model"]
            cif_block[base + "details"] = f"Located at {source_info['location']}"
            audit_id_1 = re.sub(regex, '_', source_info["manufacturer"])
            audit_id_2 = re.sub(regex, '_', source_info["model"])

        cif_block['_audit.block_code'] = audit_id_1 + '_' + audit_id_2.strip('_')


    def generate_array(self, cif_block, array_info):
        """Generate the cif_block entries for the array information.

        Produce the information required for array_structure_list. Here
        we assume a rectangular detector with x horizontal, y vertical

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            array_info (dict): information about the source
        """

        hor, vert = [float(element) for element in array_info['pixel_size']]
        base = "_array_structure_list_axis."
        cif_block[base + "axis_id"] = array_info['axis_id']
        cif_block[base + "axis_set_id"] = array_info['axis_set_id']
        cif_block[base + "displacement"] = [hor / 2, vert / 2]   #half pixel size
        cif_block[base + "displacement_increment"] = [hor, vert]
        cif_block.CreateLoop([
            base + "axis_id",
            base + "axis_set_id",
            base + "displacement",
            base + "displacement_increment"])

        base = "_array_structure_list."
        cif_block[base + "array_id"] = array_info['array_id']
        cif_block[base + "index"] = array_info['array_index']
        cif_block[base + "axis_set_id"] = array_info['axis_set_id']
        cif_block[base + "dimension"] = array_info['array_dimension']
        cif_block[base + "direction"] = array_info['array_direction']
        cif_block[base + "precedence"] = array_info['array_precedence']

        cif_block.CreateLoop([
            base + "array_id",
            base + "index",
            base + "axis_set_id",
            base + "dimension",
            base + "direction",
            base + "precedence"])


    def generate_data_frame_info(self, cif_block, scan_list):
        """Generate the cif_block entries for the data frame information.

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            scan_list (list): a list consiting of tuples with the scan name and
                the number of
        """

        base = '_diffrn_data_frame'
        entries = {
            base + ".id" : [],
            base + ".detector_element_id" : [],
            base + ".array_id" : [],
            base + ".binary_id" : [],
            }

        # TODO include the counter into element and image? where is the information
        # this probably needs the get_array_info method then
        counter = 0
        for _, frames in scan_list:
            for _ in range(1, frames + 1):
                counter += 1
                entries[base + ".id"].append(f"frm{counter}")
                entries[base + ".detector_element_id"].append(f"ELEMENT01")
                entries[base + ".array_id"].append("IMAGE01")
                entries[base + ".binary_id"].append(counter)

        for name, value in entries.items():
            cif_block[name] = value

        cif_block.CreateLoop(list(entries.keys()))


    def generate_detector(self, cif_block, detector_info):
        """Generate the cif_block entries for the detector information.

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            detector_info (dict): information about the detector
        """
        for dkey in detector_info.keys():
            print(dkey, detector_info[dkey])
        base = "_diffrn_detector."
        cif_block[base + "id"] = detector_info["detector_id"]
        cif_block[base + "number_of_axes"] = detector_info['number_of_axes'][0]
        cif_block.CreateLoop([base + "id", base + "number_of_axes"])
        base = "_diffrn_detector_axis."
        cif_block[base + "axis_id"] = detector_info['axis_id']
        cif_block[base + "detector_id"] = detector_info['detector_axis_id']
        #cif_block.CreateLoop([base + "axis_id", base + "detector_id"])

    def generate_axes(self, cif_block, axes_info):
        """Generate the cif_block entries for the axes information.

        Create the goniometer axes corresponding to the data in `raw_info`,
        placing the result in CIF block `cif_block`.

        Args:
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
            axes_info (dict): information about the axes
        """

        base = "_axis."
        cif_block[base + "id"] = axes_info['axes']
        cif_block[base + "type"] = axes_info['axis_type']
        cif_block[base + "equipment"] = axes_info['equip']
        cif_block[base + "depends_on"] = axes_info['depends_on']
        self.split_vectors(axes_info['vector'], base + "vector", cif_block)
        self.split_vectors(axes_info['offset'], base + "offset", cif_block)
        cif_block.CreateLoop([base + "id", base + "type", base + "equipment",
                              base + "depends_on",
                              base + "vector[1]", base + "vector[2]", base + "vector[3]",
                              base + "offset[1]", base + "offset[2]", base + "offset[3]"])


    def split_vectors(self, vectors, basename, cif_block):
        """
        Distribute the vectors in `vectors` over CIF data names, formatting as
        integers if they are exact.

        Args:
            vectors (list): a list of vectors which are lists of 3 entries itself
            basename (str): the basename of the imgCIF entry
            cif_block (CifFile.CifFile_module.CifBlock): the cif block into which
                the information should be written.
        """

        def mapping_func(vector):
            # i is local from the scope of the loop
            try:
                # the vector indices in cif start at 1
                vector[i - 1] = float(vector[i - 1])
                # display numbers without trailing zero? 1.0 -> 1
                if round(vector[i - 1]) == vector[i - 1]:
                    return f"{round(vector[i - 1]):.0f}"
                # don't format if it has less than 5 decimal places
                if len(str(vector[i - 1]).split('.')[1]) < 5:
                    formatted = str(vector[i - 1])
                else:
                    formatted = f"{vector[i - 1]:1.5f}"
                # it can be that some values are by computational effects
                # very close to zero e.g. -1.2246467991473532e-16 -> map to 0
                if float(formatted) == 0:
                    formatted = "0"

                return formatted
            except ValueError:
                return vector[i - 1]

        for i in range(1, 4):
            cif_block[basename + f"[{i}]"] = map(mapping_func, vectors)
