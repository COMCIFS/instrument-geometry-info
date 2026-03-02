import re

from .core import ArchiveUrl, DirectoryUrl

DOI_RULES = [
    # Download URL regex -> DOI template
    (r"https://zenodo\.org/records/(\d+)", "10.5281/zenodo.{}"),
    (r"\w+://[\w\-.]+/10\.15785/SBGRID/(\d+)", "10.15785/SBGRID/{}"),  # Various sbgrid domains
    (r"https://xrda\.pdbj\.org/rest/public/entries/download/(\d+)", "10.51093/xrd-{:05}"),
]


def guess_doi(download_info):
    """Guess a DOI for common repositories from the download URLs"""
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


def extrapolate_sequence(s0: str, s1: str, length: int):
    """Extrapolate a sequence of strings, e.g. URLs, with an embedded number"""
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
