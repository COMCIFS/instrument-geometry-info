import sys
from argparse import ArgumentParser
from pathlib import Path

import numpy as np
from dxtbx.model.experiment_list import ExperimentListFactory

from .core import ArchiveUrl, DirectoryUrl, guess_archive_type, make_cif

def parse_commandline(argv):

    ap = ArgumentParser(prog="dials2imgcif")
    ap.add_argument(
        "input_fn",
        type=Path,
        nargs='+',
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
        "--url",
        nargs="+",
        help="Full URL of archive, or one archive per scan, in order",
    )
    ap.add_argument(
        "--url-base",
        nargs="+",
        help="Individual image files can be downloaded relative to this base URL",
        metavar="url",
    )
    ap.add_argument(
        "--dir",
        type=Path,
        help="Local folder equivalent to unpacked archive(s) or URL base"
    )
    ap.add_argument(
        "-f", "--format",
        help = "Format of image files, should be one listed in imgCIF dictionary"
    )
    ap.add_argument(
        "-z", "--archive-type",
        help = "Type of overall archive, should be of type listed in imgCIF dictionary"
    )
    ap.add_argument(
        '--overload-value',
        help="Pixels with this value or above in the image data will be considered invalid"
    )
    ap.add_argument(
        '--frames-limit', metavar='N', type=int,
        help="Truncate lists to N frames (per scan), to get a preview output. "
             "The result is incomplete, so remove this option again to generate "
             "the full ImgCIF file."
    )
    ap.add_argument(
        '--no-check-format', action='store_true',
        help="Skip dxtbx checking the data file format. Needed if you don't have the "
             "data files which a DIALS .expt file points to."
    )
    args = ap.parse_args(argv)

    return args

def main(argv=None):

    if argv is None:
        argv = sys.argv[1:]

    args = parse_commandline(argv)
    out_fn = args.output_file
    if not out_fn.suffix:
        out_fn = out_fn.with_suffix('.cif')

    frame_limit = np.inf if (args.frames_limit is None) else args.frames_limit

    if args.url:
        if args.url_base:
            raise ValueError("Pass --url or --url-base, not both")
        locations = [ArchiveUrl(
            u, args.dir, (
                args.archive_type or guess_archive_type(u, warn_fail=True) or "???"
            )) for u in args.url]
    elif args.url_base:
        locations = [DirectoryUrl(u, args.dir) for u in args.url_base]
        print(locations)
    else:
        raise ValueError("--url or --url-base is required")

    if args.input_fn[0].suffix == '.expt':
        assert len(args.input_fn) == 1, "Please pass only 1 .expt file"
        expts = ExperimentListFactory.from_json_file(
            args.input_fn[0], check_format=(not args.no_check_format)
        )
    else:
        print(f"Attempting to parse {len(args.input_fn)} paths using dxtbx")
        expts = ExperimentListFactory.from_filenames(args.input_fn)
        print(f"Read {len(expts)} experiments")

    with out_fn.open('w') as outf:
        make_cif(expts, outf, out_fn.stem, locations,
                 overload_value=args.overload_value, frame_limit=frame_limit)


if __name__ == '__main__':
    main()
