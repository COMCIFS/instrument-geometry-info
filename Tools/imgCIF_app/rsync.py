import signal
from pathlib import Path
from subprocess import run, Popen, PIPE

def is_folder(url):
    if url.endswith("/"):
        return True

    res = run(["rsync", "--list-only", url], capture_output=True, text=True)
    res.check_returncode()
    return res.stdout.strip().startswith("d")


def get_file_list(url):
    res = run(["rsync", "--list-only", url], capture_output=True, text=True)
    res.check_returncode()
    lines = res.stdout.strip().splitlines(keepends=False)
    if not url.endswith("/") and len(lines) == 1 and lines[0].startswith('d'):
        # It's a directory, list its contents
        res = run(["rsync", "--list-only", url + "/"], capture_output=True, text=True)
        res.check_returncode()
        lines = res.stdout.strip().splitlines(keepends=False)

    # Tuples (mode, size, date, time, name)
    return [t for l in lines if (t := l.strip().split(None, 4))[-1] != '.']


def total_size(file_list):
    return sum(int(t[1].replace(",", "")) for t in file_list)

def download(folder_url, dest: Path):
    folder_url = folder_url.rstrip("/") + "/"  # Ensure trailing /
    popen = Popen(["rsync", "--dirs", "--info=name", folder_url, str(dest)],
                  stdin=PIPE, stdout=PIPE)
    try:
        popen.stdin.close()
        for i, line in enumerate(popen.stdout):
            yield i  # For progress monitoring
    except:
        popen.send_signal(signal.SIGTERM)
        raise
