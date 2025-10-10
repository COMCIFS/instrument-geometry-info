import argparse
import io
import re
import sys
from pathlib import Path
from subprocess import run

import h5py
import requests
from dxtbx.model import ExperimentList
from dxtbx.model.experiment_list import ExperimentListFactory
from prompt_toolkit import choice, prompt
from prompt_toolkit.validation import Validator, ValidationError

from dials2imgcif import (
    ArchiveUrl,
    DirectoryUrl,
    find_hdf5_images,
    guess_archive_type,
    guess_file_type,
    make_cif,
)

# Recognised formats for ImgCIF
ARCHIVE_TYPES = ("TGZ", "TBZ", "TXZ", "ZIP")
FILE_TYPES = ("HDF5", "CBF", "TIFF", "SMV")


class URLValidator(Validator):
    def validate(self, document):
        url = document.text
        cp = document.cursor_position

        try:
            resp = requests.get(url, stream=True)
        except requests.RequestException as e:
            raise ValidationError(message=f"Bad URL ({e})", cursor_position=cp)
        else:
            if resp.status_code >= 400:
                raise ValidationError(
                    message=f"Bad URL ({resp.status_code}: {resp.reason})",
                    cursor_position=cp,
                )


class DOIValidator(Validator):
    def __init__(self, known_ok=()):
        self.known_ok = known_ok

    def validate(self, document):
        doi = document.text
        if not doi:
            return

        if doi in self.known_ok:
            return

        cp = document.cursor_position
        try:
            resp = requests.get(f"https://doi.org/{doi}", stream=True)
        except requests.RequestException as e:
            raise ValidationError(message=f"Bad DOI ({e})", cursor_position=cp)
        else:
            if resp.status_code >= 400:
                raise ValidationError(
                    message=f"Bad DOI ({resp.status_code}: {resp.reason})",
                    cursor_position=cp,
                )


DOI_RULES = [
    # Download URL regex -> DOI template
    (r"https://zenodo\.org/records/(\d+)", "10.5281/zenodo.{}"),
    (r"\w+://[\w\-.]+/10\.15785/SBGRID/(\d+)", "10.15785/SBGRID/{}"),  # Various sbgrid domains
    (r"https://xrda\.pdbj\.org/rest/public/entries/download/(\d+)", "10.51093/xrd-{:05}"),
]


def guess_doi(download_info):
    urls = []
    for loc in download_info:
        if isinstance(loc, ArchiveUrl):
            urls.append(loc.url)
        elif isinstance(loc, DirectoryUrl):
            urls.append(loc.url_base)

    if not urls:
        return ""

    for url_pat, doi_template in DOI_RULES:
        matches = [re.match(url_pat, u) for u in urls]
        if all(matches):
            id_part = matches[0][1]
            if all(m[1] == id_part for m in matches[1:]):
                return doi_template.format(id_part)

    return ""


def check_url(url, msg="Checking URL..."):
    print(msg, end=" ", flush=True)
    try:
        resp = requests.get(url, stream=True)
    except requests.RequestException as e:
        print(e)
    else:
        if resp.status_code >= 400:
            print(resp.status_code, resp.reason)
        else:
            print("OK")
            return True
    return False


def input_url_validated(p):
    return prompt(p, validator=URLValidator(), validate_while_typing=False)


def input_archive_type(url: str):
    return choice("Archive type:", options=[
        ("TGZ", "TGZ - .tar.gz"),
        ("TBZ", "TBZ - .tar.bz2"),
        ("TXZ", "TXZ - .tar.xz"),
        ("ZIP", "ZIP - .zip"),
    ], default=guess_archive_type(url))


def input_file_type(name: str, dxtbx_fmt_cls):
    guess = guess_file_type(name, dxtbx_fmt_cls)
    return choice("File type:", options=[
        ("HDF5", "HDF5 (including NeXus files)"),
        ("CBF", "CBF"),
        ("TIFF", "TIFF"),
        ("SMV", "SMV"),
    ], default=guess_file_type(name, dxtbx_fmt_cls))

def choose_archive_unpacked_root(file_path: Path) -> Path:
    chosen = choice("Paths inside archive:", options=[
        (i, f"{file_path.relative_to(p)}\n      Unpacked root: {p}")
        for i, p in enumerate(file_path.parents[:-1])
    ])
    return file_path.parents[chosen]


def find_common_ancestor(p1: Path, p2: Path):
    for candidate in p1.parents:
        if p2.is_relative_to(candidate):
            return candidate
    raise ValueError(f"No ancestor in common: {p1} & {p2}")


def extrapolate_sequence(s0, s1, length):
    matched0 = re.split(r"(\d+)", s0)
    matched1 = re.split(r"(\d+)", s1)
    if len(matched0) != len(matched1):
        return

    if (
        len(
            diffs := [
                i for i, (p0, p1) in enumerate(zip(matched0, matched1)) if p0 != p1
            ]
        )
        != 1
    ):
        return  # No difference, or >1 piece differs
    if (diff_ix := diffs[0]) % 2 == 0:
        return  # The difference is in a non-numeric part

    width = len(matched0[diff_ix])
    n0 = int(matched0[diff_ix])  # First number in sequence
    if int(matched1[diff_ix]) != n0 + 1:
        return  # Not increasing by 1

    for i in range(2, length):
        pieces = matched0.copy()
        pieces[diff_ix] = f"{n0 + i:0{width}}"
        yield "".join(pieces)


def get_download_urls(expts: ExperimentList):
    opt = choice("Is the data downloaded as:", options=[
        ("single", "A single archive (e.g. .zip or .tar.gz)"),
        ("scans",  "One archive per scan"),
        ("separate", "Separate files, not in an archive"),
    ])

    first_path = Path(expts[0].imageset.get_path(0))
    if opt == "single":  # Single archive
        url = input_url_validated("Archive URL: ")
        archive_type = input_archive_type(url)
        base_dir = choose_archive_unpacked_root(first_path)
        print("Archive is unpacked at:", base_dir)
        return [ArchiveUrl(url, base_dir, archive_type)]
    elif opt == "scans":  # Archive per scan
        res = []

        print(f"Scan 1, starting with file {first_path}")
        first_url = input_url_validated("Archive URL: ")
        archive_type = input_archive_type(first_url)
        first_base_dir = choose_archive_unpacked_root(first_path)
        res.append(ArchiveUrl(first_url, first_base_dir, archive_type))
        print()
        if len(expts) <= 1:
            return res

        second_path = Path(expts[1].imageset.get_path(0))
        print(f"Scan 2, starting with file {second_path}")
        second_url = input_url_validated("Archive URL: ")
        second_base_dir = choose_archive_unpacked_root(second_path)
        res.append(ArchiveUrl(second_url, second_base_dir, archive_type))
        print()
        if len(expts) <= 2:
            return res

        more_urls = list(extrapolate_sequence(first_url, second_url, len(expts)))
        if not more_urls:
            print("Could not find sequence from URLs")
        if second_base_dir == first_base_dir:
            more_base_dirs = [first_base_dir] * (len(expts) - 2)
        else:
            more_base_dirs = [
                Path(p)
                for p in extrapolate_sequence(
                    str(first_base_dir), str(second_base_dir), len(expts)
                )
            ]
            if not more_base_dirs:
                print("Could not find sequence from unpacked archive roots")

        for i in range(2, len(expts)):
            if more_urls:
                url = more_urls[i - 2]
                print(f"Scan {i + 1} URL:", url)
                if i == len(expts) - 1:
                    if not check_url(url):
                        sys.exit(1)
            else:
                url = input_url_validated(f"Scan {i + 1} URL: ")

            if more_base_dirs:
                base_dir = more_base_dirs[i - 2]
                print("  Unpacked as:", base_dir)
                if not base_dir.is_dir():
                    sys.exit("Not a directory")
            else:
                eg_path = expts[i].imageset.get_path(0)
                base_dir = choose_archive_unpacked_root(eg_path)

            res.append(ArchiveUrl(url, base_dir, archive_type))

        return res

    else:  # Separate files
        if h5py.is_hdf5(first_path):
            first_path, *_ = next(find_hdf5_images(first_path))
        print("First data file:")
        print(" ", first_path)
        first_url = input_url_validated("URL for this file: ")

        last_path = Path(expts[-1].imageset.get_path(len(expts[-1].imageset) - 1))
        if h5py.is_hdf5(last_path):
            last_path, *_ = list(find_hdf5_images(last_path))[-1]

        base_dir = find_common_ancestor(first_path, last_path)
        levels_under_base = len(first_path.relative_to(base_dir).parts)
        base_url = first_url.rsplit("/", levels_under_base)[0]
        last_url = f"{base_url}/{last_path.relative_to(base_dir).as_posix()}"

        print("Last path:", last_path)
        print(f"Last URL (extrapolated):\n  {last_url}")
        if not check_url(last_url):
            sys.exit(1)
        print()

        print("Base URL:", base_url)
        print("Directory:", base_dir)
        return [DirectoryUrl(base_url, base_dir)]


def get_doi(download_info):
    guessed = guess_doi(download_info)
    if guessed:
        print("Data DOI (guessed from download URLs):", guessed)
        if not check_url(f"https://doi.org/{guessed}", "Checking DOI resolves..."):
            guessed = ""

    return prompt(
        "DOI (optional): ",
        default=guessed,
        validator=DOIValidator(known_ok=(guessed,) if guessed else ()),
        validate_while_typing=False,
    ) or None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()

    if args.files[0].suffix == ".expt":
        assert len(args.files) == 1, "Please pass only 1 .expt file"
        expts = ExperimentListFactory.from_json_file(
            args.files[0], check_format=True  # (not args.no_check_format)
        )
    else:
        print(f"Attempting to parse {len(args.files)} paths using dxtbx")
        expts = ExperimentListFactory.from_filenames(args.files)

    print(
        f"Found {len(expts)} experiment(s) with "
        f"{sum(len(e.imageset) for e in expts)} total images.\n"
    )

    download_info = get_download_urls(expts)
    print()

    doi = get_doi(download_info)
    print()

    imgset0 = expts[0].imageset
    file_type = input_file_type(imgset0.get_path(0), imgset0.get_format_class())
    print()

    sio = io.StringIO()
    sio.write("# ImgCIF preview - press Q to go back\n\n")
    make_cif(
        expts,
        sio,
        data_name="preview",
        locations=download_info,
        doi=doi,
        file_type=file_type,
        overload_value=None,
        frame_limit=5,
    )

    run(["less"], input=sio.getvalue().encode("utf-8"))

    out_filename = Path(prompt("Output filename: ", default="generated.cif"))

    if out_filename.is_file():
        rep = prompt(
            "Overwrite (y/n): ", default="y",
            validator=Validator.from_callable(lambda s: s.lower() in ("y", "n"))
        ).lower()
        if rep == "n":
            print("No output written")
    elif out_filename.exists():
        sys.exit(f"{out_filename} exists but is not a file")

    with out_filename.open("w", encoding="utf-8") as f:
        make_cif(
            expts,
            f,
            data_name=out_filename.stem,
            locations=download_info,
            doi=doi,
            file_type=file_type,
            overload_value=None,
        )
    print(f"Written {out_filename}")


if __name__ == "__main__":
    sys.exit(main())
