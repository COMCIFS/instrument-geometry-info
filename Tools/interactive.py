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

from dials2imgcif import make_cif, ArchiveUrl, DirectoryUrl, find_hdf5_images


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


def input_url_validated(prompt):
    while True:
        url = input(prompt)
        if check_url(url):
            return url


def guess_archive_type(url: str):
    if url.endswith((".tgz", ".tar.gz")):
        return "TGZ"
    elif url.endswith((".tbz", ".tar.bz2")):
        return "TBZ"
    elif url.endswith((".txz", ".tar.xz")):
        return "TXZ"
    elif url.endswith(".zip"):
        return "ZIP"

    return None


def input_archive_type(url: str):
    guess = guess_archive_type(url)
    dflt = f" [{guess}]" if guess else ""
    while True:
        res = input(f"Archive type (TGZ, TBZ, TXZ, ZIP){dflt}: ").upper() or guess
        if res in ("TGZ", "TBZ", "TXZ", "ZIP"):
            return res


def choose_archive_unpacked_root(file_path: Path) -> Path:
    print("The archive is unpacked as:")
    n_levels = len(file_path.parents)
    for i, p in enumerate(file_path.parents[:3], start=1):
        print(f" {i}. {p}")
        print(f"   Path in archive: {file_path.relative_to(p)}")
    if n_levels > 3:
        if n_levels > 4:
            print(f" ... up to {n_levels} ({file_path.parents[-1]})")

    while True:
        choice = input(f"Option 1-{n_levels}: ")
        try:
            choice = int(choice)
        except ValueError:
            continue

        if 1 <= choice <= n_levels:
            return file_path.parents[choice - 1]


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
    print("Is the data downloaded as:")
    print(" 1. A single archive (e.g. .zip or .tar.gz)")
    print(" 2. One archive per scan")
    print(" 3. Separate files, not in an archive")

    choice = ""
    while choice not in ("1", "2", "3"):
        choice = input("Option 1-3: ")

    first_path = Path(expts[0].imageset.get_path(0))
    if choice == "1":  # Single archive
        url = input_url_validated("Archive URL: ")
        archive_type = input_archive_type(url)
        base_dir = choose_archive_unpacked_root(first_path)
        print("Archive is unpacked at:", base_dir)
        return [ArchiveUrl(url, base_dir, archive_type)]
    elif choice == "2":  # Archive per scan
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
        return DirectoryUrl(base_url, base_dir)


def get_doi(download_info):
    guessed = guess_doi(download_info)
    if guessed:
        print("Data DOI (guessed from download URLs):", guessed)
        if not check_url(f"https://doi.org/{guessed}", "Checking DOI resolves..."):
            guessed = ""

    if guessed:
        print("1. Use guessed DOI", guessed)
        print("2. Enter another DOI for the data")
        print("3. No DOI")
        choice = ""
        while choice not in ("1", "2", "3"):
            choice = input("Option 1-3: ")

        if choice == "1":
            return guessed
        elif choice == "3":
            return None

    while True:
        doi = input("DOI (optional): ")
        if not doi:
            print("No DOI will be included")
            return None

        if check_url(f"https://doi.org/{doi}", "Checking DOI resolves..."):
            return doi


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

    sio = io.StringIO()
    sio.write("# ImgCIF preview - press Q to go back\n\n")
    make_cif(
        expts,
        sio,
        data_name="preview",
        locations=download_info,
        doi=doi,
        file_type=None,
        overload_value=None,
        frame_limit=5,
    )

    run(["less"], input=sio.getvalue().encode("utf-8"))

    out_filename = Path(input("Output filename [generated.cif]: ") or "generated.cif")

    if out_filename.is_file():
        rep = ""
        while rep not in ("y", "n"):
            rep = input("Overwrite ([y]/n): ").lower() or "y"
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
            file_type=None,
            overload_value=None,
            frame_limit=5,
        )
    print(f"Written {out_filename}")


if __name__ == "__main__":
    sys.exit(main())
