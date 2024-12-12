"""The main stript to call the imgCIF creator.
"""

import sys
import os
import re
import click
import CifFile
from imgCIF_Creator.output_creator import imgcif_creator
from imgCIF_Creator.command_line_interfaces import parser



def validate_filename(filename):
    """Checks if the input string is a) a folder containing cbf or smv files or
    b) is a h5 filename, otherwise exits the program. Only the top level directory
    is checked.

    Args:
        filename (str): the name of the folder containing the files or the filename
    """

    if os.path.isdir(filename):
        for root, dirs, files in os.walk(filename + os.sep):
            pattern = re.compile(r'.*((?P<cbf>\.cbf)\Z|(?P<smv>\.(smv|img))\Z)')
            matches = [pattern.match(file) for file in files]
            matches = [match for match in matches if match is not None]
            occurences = len(matches)
            if occurences > 0:
                if matches[0]["cbf"] is not None:
                    filetype = "cbf"
                else:
                    filetype = "smv"

                print(f'Found {occurences} {filetype} files in {root}.')
                
            else:
                print(f'Could not find cbf or smv files in {root}. Subfolder(s) \
{dirs} are not considered automatically.')
                sys.exit()
            # check only top level dir
            break
    elif os.path.isfile(filename):
        filetype = None
        supported_filetypes = ['h5', 'expt']
        regexs = [r'.*((?P<h5>\.h5)\Z)', r'.*((?P<expt>\.expt)\Z)']
        for i, regex in enumerate(regexs):
            match = re.match(regex, filename)
            if match is not None:
                filetype = supported_filetypes[i]
                break
        if not filetype:
            print('Only h5 (NxMx) and expt (DIALS) files are supported! \
If you want to convert cbf and smv files please provide a directory. Exiting.')
            sys.exit()
    else:
        print(f'{filename} is neither a valid directory nor filename!')
        sys.exit()

    return filename, filetype



# # This changes an axis name and should be done according to the header info
# @click.option(
#     "--axis",
#     "-a",
#     default=None,
#     type=list,
#     help="Change axis name from <cbf> to <new> in output, to match the goniometer\
# axis definitions. May be used multiple times for multiple axis renaming."
# )

@click.command()
# @click.option(
#     "--gui",
#     "-g",
#     default=False,
#     type=bool,
#     is_flag=True,
#     help="Start the imgcif_creator with a graphical user interface.",
# )

# @click.option(
#     "--external_url",
#     "-u",
#     type=str,
#     default='',
#     help='Final URL of files in output.'
# )
# this changed previously the uri, which is the file location before into the value
# specified here
# e.g. file://cbf_cyclohexane_crystal2/CBF_crystal_2/ciclohexano3_010001.cbf -->
# my_new_name/ciclohexano3_010001.cbf

# @click.option(
#     "--include",
#     "-i",
#     type=bool,
#     default=False,
#     is_flag=True,
#     help="Include the directory name as part of the archive path name."
# )
# this only has an effect if the location is set and has a archive archive_path
# as tgz then _array_data_external_data.archive_path is filled and if i is
# selected the folder name is prepended to that name

@click.option(
    "--stem",
    "-s",
    type=str,
    default=r".*?_",
    help="Constant portion of frame file name. This can help determine the \
scan/frame file naming convention",
)

@click.option(
    "--output_file",
    "-o",
    type=str,
    default='',
    help="Output file to write to."
)

@click.argument(
    "filename",
    type=str,
    # help="The filename of the file that should be converted",
    # callback=validate_filename,
)

def main(filename, stem, output_file):
    """This is an interactive command line interface to collect the necessary
information to create an imgCIF file out of HDF5, full CBF and some common subset
of miniCBF.

Arguments:\n
    filename (str): A file name or directory.\n
    stem (str): Constant portion of the file names in case of multiple frames.\n
    output_file (str): Output file to write to.
    """

    print('\n--------------------------- imgCIF Creator ---------------------------\n')
    print("""This is an interactive command line interface to collect the necessary
information to create an imgCIF file out of full CBF files and some common
subsets of miniCBF and HDF5 master files.

Parameters that are missing in the provided file or directory will be requested
from the user. You can skip parameters that are not required with an empty input,
if you provide an input it will be checked against the required format.
""")

    filename, filetype = validate_filename(filename)
    print(f'Identified content of {filename} as {filetype} file(s).')

    command_line_interface(filename, filetype, stem, output_file)


def command_line_interface(filename, filetype, stem, output_file):
    """Launch the command line interface to interactively create the imgCIF.

    Args:
        filename (str): the filename or directory name where the data is located
        filetype (str): the filetype of the files, either cbf or h5
        external_url (str): the external file url provided by the user
        stem (str): Constant portion of frame file name. This can help determine the \
            scan/frame file naming convention
        output_file (str): output file to write to
    """

    cif_file = CifFile.CifFile()
    cif_block = CifFile.CifBlock()
    name = parser.CommandLineParser().request_input('name')
    if name == '':
        name = filename.split(os.sep)[-1].strip('.h5')
    cif_file[name] = cif_block

    creator = imgcif_creator.ImgCIFCreator(filename, filetype, stem)
    creator.create_imgcif(cif_block, filename, filetype)

    if output_file == '':
        output_file = os.getcwd() + os.sep + name + '.cif'
    else:
        if not output_file.endswith('.cif'):
            output_file = output_file + '.cif'

    # change some ordering
    if cif_file[name].get('_database.dataset_doi') is not None:
        cif_file[name].ChangeItemOrder('_database.dataset_doi', 0)
    if cif_file[name].get('_audit.block_code') is not None:
        cif_file[name].ChangeItemOrder('_audit.block_code', 1)

    with open(output_file, 'w') as file:
        print('\nRequired input completed! \n')
        # setting wraplength and maxoutlength does not have an effect
        # wraplength=1000
        file.write(cif_file.WriteOut())
        print(f'Created imgCIF and saved to: {output_file}\n')

