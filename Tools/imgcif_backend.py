import io
import json
import re
import socket
import sys
import traceback
from pathlib import Path

from dxtbx.model import Experiment, ExperimentList, MultiAxisGoniometer
from dxtbx.model.experiment_list import ExperimentListFactory
from dials2imgcif import (
    guess_file_type, guess_archive_type, make_cif, ArchiveUrl, DirectoryUrl, PlaceholderUrl
)

DOI_RULES = [
    (r"https://zenodo\.org/records/(\d+)", "10.5281/zenodo.{}"),
    (r"\w+://[\w\-.]+/10\.15785/SBGRID/(\d+)", "10.15785/SBGRID/{}"),  # Various sbgrid domains
    (r"https://xrda\.pdbj\.org/rest/public/entries/download/(\d+)", "10.51093/xrd-{:05}"),
]


def line_helper(sock):
    read_buffer = []
    while True:
        if not (b := sock.recv(4096)):
            return
        while b'\n' in b:
            line_end, _, b = b.partition(b'\n')
            yield b''.join(read_buffer + [line_end])
            read_buffer = []
        read_buffer.append(b)

class Backend:
    COMMANDS = {'reset', 'add_paths', 'set_expt', 'set_download_files', 'set_download_archives', 'set_doi'}

    def __init__(self):
        self.expt_list: ExperimentList = ExperimentList([])
        self.download_locations = [PlaceholderUrl()]
        self.explicit_doi = None

    def reset(self):
        self.expt_list = ExperimentList([])

    def add_paths(self, paths):
        self.expt_list.extend(ExperimentListFactory.from_filenames(paths))

    def set_expt(self, path):
        try:
            self.expt_list = ExperimentListFactory.from_json_file(path)
        except FileNotFoundError:
            self.expt_list = ExperimentListFactory.from_json_file(path, check_format=False)

    def set_download_files(self, url):
        url_base = url.rpartition('/')[0]
        self.download_locations = [DirectoryUrl(url_base)]

    def set_download_archives(self, url, local_dir, archive_type=None):
        self.download_locations = [ArchiveUrl(
            url, local_dir, archive_type or guess_archive_type(url)
        )]

    def set_doi(self, doi):
        self.explicit_doi = doi

    def guess_doi(self):
        urls = []
        for loc in self.download_locations:
            if isinstance(loc, ArchiveUrl):
                urls.append(loc.url)
            elif isinstance(loc, DirectoryUrl):
                urls.append(loc.url_base)

        if not urls:
            return ""

        for url_pat, doi_template in DOI_RULES:
            matches = [re.match(url_pat, u) for u in urls]
            print(matches)
            if all(matches):
                id_part = matches[0][1]
                if all(m[1] == id_part for m in matches[1:]):
                    return doi_template.format(id_part)

        return ""

    def state(self):
        if self.expt_list:
            sio = io.StringIO()
            try:
                make_cif(self.expt_list, sio, data_name='preview',
                         locations=self.download_locations, frame_limit=5)
            except Exception:
                traceback.print_exc()
                preview = None
            else:
                preview = sio.getvalue()

            expt0 = self.expt_list[0]
            path0 = Path(expt0.imageset.get_template())
            file_type = guess_file_type(path0.name, expt0.imageset.get_format_class())
        else:
            file_type = preview = ""

        return {
            'n_expts': len(self.expt_list),
            'expt_summaries': [self.experiment_description(e) for e in self.expt_list],
            'n_frames': sum([e.scan.get_num_images() for e in self.expt_list]),
            'file_type': file_type,
            'doi_set': bool(self.explicit_doi),
            'doi': (self.explicit_doi or self.guess_doi()),
            'cif_preview': preview,
        }

    @staticmethod
    def experiment_description(expt: Experiment):
        n_images = expt.scan.get_num_images()
        start, step = expt.scan.get_oscillation()
        full_range = step * n_images  # to end of final step
        if isinstance(expt.goniometer, MultiAxisGoniometer):
            gonio_names = expt.goniometer.get_names()
            scan_ax = gonio_names[expt.goniometer.get_scan_axis()] + " "
        else:
            scan_ax = ""
        return f"{full_range:.0f}° {scan_ax}scan ({n_images} frames)"

def main():
    sock_fd = int(sys.argv[1])
    sock = socket.socket(fileno=sock_fd)
    backend = Backend()
    print("Backend: started")

    for line in line_helper(sock):
        command, kwargs = json.loads(line)
        print(f"Backend: got command {command!r}")
        try:
            assert command in backend.COMMANDS, f"Bad command: {command!r}"
            getattr(backend, command)(**kwargs)
        except Exception:
            traceback.print_exc()
        else:
            state_b = json.dumps(['state', backend.state()], indent=None).encode('utf-8') + b'\n'
            sock.sendall(state_b)

    print("Backend: exiting")

if __name__ == '__main__':
    main()
