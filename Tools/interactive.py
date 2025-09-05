import argparse
import sys
from pathlib import Path

import h5py
import requests
from dxtbx.model import ExperimentList
from dxtbx.model.experiment_list import ExperimentListFactory

from dials2imgcif import make_cif, ArchiveUrl, DirectoryUrl, find_hdf5_images

def check_url(url):
    print("Checking URL...", end=" ", flush=True)
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
    if url.endswith(('.tgz', '.tar.gz')):
        return 'TGZ'
    elif url.endswith(('.tbz', '.tar.bz2')):
        return 'TBZ'
    elif url.endswith(('.txz', '.tar.xz')):
        return 'TXZ'
    elif url.endswith('.zip'):
        return 'ZIP'

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
        ...
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




def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()

    if args.files[0].suffix == '.expt':
        assert len(args.files) == 1, "Please pass only 1 .expt file"
        expts = ExperimentListFactory.from_json_file(
            args.files[0], check_format=True #(not args.no_check_format)
        )
    else:
        print(f"Attempting to parse {len(args.files)} paths using dxtbx")
        expts = ExperimentListFactory.from_filenames(args.files)

    print(f"Found {len(expts)} experiment(s) with "
          f"{sum(len(e.imageset) for e in expts)} total images.\n")

    get_download_urls(expts)

if __name__ == "__main__":
    sys.exit(main())
