"""Turn a saved PCSO 'Search Lotto Result' page (.htm) into a CSV that import_results.py can read.

Usage:
    python parse_pcso_page.py Philippine_Charity_Sweepstakes_Office_new.htm pcso_page_results.csv
"""
import csv
import html
import re
import sys

TABLE_RE = re.compile(r'<table[^>]*search-lotto-result-table.*?</table>', re.S | re.I)


def clean(cell_html):
    return html.unescape(re.sub(r"<[^>]+>", "", cell_html)).strip()


def main(src, dest):
    page = open(src, encoding="utf-8", errors="replace").read()
    table = TABLE_RE.search(page)
    if not table:
        sys.exit("Results table not found - was the page saved after clicking 'Search Lotto'?")
    rows = []
    for tr in re.findall(r"<tr.*?</tr>", table.group(0), re.S | re.I):
        cells = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if cells:
            rows.append(cells)
    with open(dest, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    print(f"Wrote {len(rows) - 1} result rows to {dest}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
