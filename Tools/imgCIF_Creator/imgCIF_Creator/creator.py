import sys
import click
import os
import re
import CifFile
from imgCIF_Creator.output_creator import imgCIF_creator
from imgCIF_Creator.command_line_interfaces import parser



def validate_filename(filename):
    """_summary_

    Args:
        filename (_type_): _description_
    """

    if os.path.isdir(filename):
        for _, _, files in os.walk(filename + os.sep):
            pattern = re.compile(r'.*((?P<cbf>\.cbf)\Z|(?P<smv>\.smv)\Z)')
            matches = [bool(pattern.match(file)) for file in files]
            occurences = len([match for match in matches if match == True])
            if occurences > 0:
                print('Found a folder with .cbf or .smv files.')
                filetype = 'cbf'
            else:
                print('Could not find .cbf or .smv files in directory.')
                sys.exit()
    elif os.path.isfile(filename):
        regex = r'.*((?P<h5>\.h5)\Z)'
        match = re.match(regex, filename)
        filetype = 'h5'
        if not match:
            print('Only h5 (NxMx) files are supported! If you want to convert \
.cbf and .smv files please provide a directory. Exiting.')
            sys.exit()
    else:
        print('Could not find a cbf, smv or hdf5 file for the given file or directory!')
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
@click.option(
    "--gui",
    "-g",
    default=False,
    type=bool,
    is_flag=True,
    help="Start the imgCIF_creator with a graphical user interface.",
)

@click.option(
    "--external_url",
    "-u",
    type=str,
    default='',
    help='Final URL of files in output.'
)
# this changed previously the uri, which is the file location before into the value
# specified here
# e.g. file://cbf_cyclohexane_crystal2/CBF_crystal_2/ciclohexano3_010001.cbf -->
# my_new_name/ciclohexano3_010001.cbf

@click.option(
    "--include",
    "-i",
    type=bool,
    default=False,
    is_flag=True,
    help="Include the directory name as part of the archive path name."
)
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

def main(filename, gui, external_url, include, stem, output_file):
    """This is an interactive command line interface to collect the necessary
information to create an imgCIF file out of HDF5, full CBF and some common subset
of miniCBF

    Args:
        filename (str): The filename or directory.
        gui (bool): Whether to use the gui or the command line.
        external_url (str): The external url of the files (zenodo url)
        include (bool): Include the directory name as part of the archive path name.
        stem (str): Constant portion of frame file name.
        output_file (str): Output file to write to.
    """
    # stem = '010_Ni_dppe_Cl_2_150K'
    # stem = r".*?_"

    print('\n--------------------------- imgCIF Creator ---------------------------\n' )
    print("""This is an interactive command line interface to collect the necessary
information to create an imgCIF file out of HDF5, full CBF and some common subset
of miniCBF.

Parameters that are missing in the provided file or directory will be requested
from the user. You can skip parameters that are not required with an empty input,
if you provide an input it will be checked against the required format.
""")

    filename, filetype = validate_filename(filename)
    print(f'Identified {filename}, as {filetype} file.')

    if include:
        prepend_dir = os.path.split(filename)[-1]
    else:
        prepend_dir = ""

    if gui:
        graphical_user_interface()
    else:
        command_line_interface(
            filename, filetype, external_url, prepend_dir, stem, output_file)


def command_line_interface(filename, filetype, external_url, prepend_dir, stem,
        output_file):


    cif_file = CifFile.CifFile()
    cif_block = CifFile.CifBlock()
    name = parser.CommandLineParser().request_input('name')
    name = name if name != '' else 'myimgcif'
    cif_file[name] = cif_block

    creator = imgCIF_creator.imgCIFCreator(filename, filetype, stem)
    creator.create_imgCIF(
        cif_block, external_url, prepend_dir, filename, filetype)

    if output_file == '':
        output_file = os.getcwd() + os.sep + name + '.cif'
    else:
        if not output_file.endswith('.cif'):
            output_file = output_file + '.cif'

    with open(output_file, 'w') as file:
        print('\nRequired input completed! \n')
        # setting wraplength and maxoutlength does not have an effect
        # wraplength=1000
        file.write(cif_file.WriteOut())
        print(f'Created imgCIF and saved to: {output_file}\n')


def graphical_user_interface():

    print('GUI not implemented yet!')