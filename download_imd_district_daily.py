#!/usr/bin/env python3
"""
IMD District Rainfall Downloader & Merger
==========================================

What this does, every time you run it:
  1. Downloads the latest "District Rainfall Distribution (Daily & Cumulative)"
     PDF published by IMD (same URL every day -> content updates in place):
     https://mausam.imd.gov.in/Rainfall/DISTRICT_RAINFALL_DISTRIBUTION_COUNTRY_INDIA_cd.pdf
  2. Parses the PDF text into structured rows (State + District level).
  3. Merges those rows onto your master CSV (columns: State, District, Lat, Lon)
     by matching State + District names (case/whitespace-insensitive).
  4. Writes a dated output CSV, e.g. output/rainfall_2026-07-22.csv
     (the date used is the "DAY:" date printed inside the PDF itself, so the
     filename reflects the data date, not just whenever the script happened to run).

Final CSV columns:
  State, District, Lat, Lon, Actual, Normal, Dept, Category,
  Cumulative_Actual, Cumulative_Normal, Cumulative_Dept, Cumulative_Category

Usage:
  python imd_rainfall_update.py --main-csv master.csv --out-dir output

Designed to run unattended in GitHub Actions (see the workflow YAML at the
bottom of this file, in the comment block) — no manual input needed.

Dependencies:
  pip install requests pdfplumber pandas
"""

import argparse
import io
import os
import re
import sys
from datetime import datetime

import pandas as pd
import requests

try:
    import pdfplumber
except ImportError:
    print("Missing dependency 'pdfplumber'. Install with: pip install pdfplumber", file=sys.stderr)
    raise

PDF_URL = "https://mausam.imd.gov.in/Rainfall/DISTRICT_RAINFALL_DISTRIBUTION_COUNTRY_INDIA_cd.pdf"

NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")
DAY_RE = re.compile(r"DAY:\s*(\d{2})-(\d{2})-(\d{4})")

SKIP_PREFIXES = (
    "India Meteorological Department",
    "Hydromet Division",
    "DISTRICT RAINFALL DISTRIBUTION",
    "DAY:",
    "S.No",
    "LEGEND",
    "CATEGORY",
    "Note :",
    "Large Excess",
    "Excess (",
    "Normal (",
    "Deficient (",
    "Large Deficient",
    "No Rain",
    "Not Available",
)


def download_pdf(url: str, dest_path: str) -> str:
    """Download the PDF to dest_path. Raises on HTTP error."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; IMDRainfallBot/1.0)"}
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(resp.content)
    return dest_path


def extract_data_date(first_page_text: str) -> str:
    """Pull the 'DAY: DD-MM-YYYY' date out of the PDF and return YYYY-MM-DD."""
    m = DAY_RE.search(first_page_text or "")
    if m:
        dd, mm, yyyy = m.groups()
        return f"{yyyy}-{mm}-{dd}"
    return datetime.utcnow().strftime("%Y-%m-%d")


def split_name_and_values(line: str):
    """
    Split a data line into (name, value_tokens).
    The name is everything before the first token that is a plain number
    or the literal 'ND'. Returns (None, None) if no such token exists
    (i.e. the line isn't a data row at all -- header/footer/legend text).
    """
    tokens = line.split()
    for i, tok in enumerate(tokens):
        if tok == "ND" or NUM_RE.match(tok):
            name = " ".join(tokens[:i]).strip()
            if not name:
                return None, None
            return name, tokens[i:]
    return None, None


def parse_block(tokens, idx):
    """
    Parse one ACTUAL/NORMAL/%DEP/CAT block starting at tokens[idx].
    If NORMAL == 'ND', the %DEP and CAT fields are absent in the source
    (IMD simply omits them), so we only consume ACTUAL + 'ND'.
    Returns (dict, new_idx).
    """
    actual = tokens[idx]
    idx += 1
    normal = tokens[idx]
    idx += 1
    if normal == "ND":
        return {"actual": _to_num(actual), "normal": None, "dep": None, "cat": None}, idx
    dep = tokens[idx]
    idx += 1
    cat = tokens[idx]
    idx += 1
    return {"actual": _to_num(actual), "normal": _to_num(normal), "dep": _to_num(dep), "cat": cat}, idx


def _to_num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_pdf(pdf_path: str):
    """
    Parse the IMD district rainfall PDF.
    Returns (data_date_str, list_of_row_dicts).
    Each row dict: State, District (None for state/subdivision summary rows),
    Actual, Normal, Dept, Category, Cumulative_Actual, Cumulative_Normal,
    Cumulative_Dept, Cumulative_Category, IsState (bool)
    """
    rows = []
    current_state = None
    data_date = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if page_num == 0:
                data_date = extract_data_date(text)

            for raw_line in text.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue
                if any(line.startswith(p) for p in SKIP_PREFIXES):
                    continue

                m = re.match(r"^(\d+)\s+(.*)$", line)
                if m:
                    # District-level row: "<S.No> <District Name> <values...>"
                    rest = m.group(2)
                    name, values = split_name_and_values(rest)
                    if name is None or len(values) < 4:
                        continue
                    try:
                        daily, idx = parse_block(values, 0)
                        cum, _ = parse_block(values, idx)
                    except IndexError:
                        continue
                    rows.append({
                        "State": current_state,
                        "District": name,
                        "Actual": daily["actual"], "Normal": daily["normal"],
                        "Dept": daily["dep"], "Category": daily["cat"],
                        "Cumulative_Actual": cum["actual"], "Cumulative_Normal": cum["normal"],
                        "Cumulative_Dept": cum["dep"], "Cumulative_Category": cum["cat"],
                        "IsState": False,
                    })
                else:
                    # State / subdivision summary row (no S.No)
                    name, values = split_name_and_values(line)
                    if name is None or len(values) < 4:
                        continue
                    try:
                        daily, idx = parse_block(values, 0)
                        cum, _ = parse_block(values, idx)
                    except IndexError:
                        continue
                    current_state = name  # districts that follow belong to this state
                    rows.append({
                        "State": name,
                        "District": None,
                        "Actual": daily["actual"], "Normal": daily["normal"],
                        "Dept": daily["dep"], "Category": daily["cat"],
                        "Cumulative_Actual": cum["actual"], "Cumulative_Normal": cum["normal"],
                        "Cumulative_Dept": cum["dep"], "Cumulative_Category": cum["cat"],
                        "IsState": True,
                    })

    return data_date, rows


def normalize(s):
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip().upper()


def merge_with_master(master_csv: str, rows: list) -> pd.DataFrame:
    """Merge parsed district rows onto the master State/District/Lat/Lon CSV."""
    master = pd.read_csv(master_csv)
    required = {"State", "District", "Lat", "Lon"}
    missing = required - set(master.columns)
    if missing:
        raise ValueError(f"Main CSV is missing required columns: {missing}")

    district_rows = [r for r in rows if not r["IsState"]]
    lookup = {}
    for r in district_rows:
        key = (normalize(r["State"]), normalize(r["District"]))
        lookup[key] = r

    out_cols = ["Actual", "Normal", "Dept", "Category",
                "Cumulative_Actual", "Cumulative_Normal", "Cumulative_Dept", "Cumulative_Category"]

    matched = {c: [] for c in out_cols}
    unmatched = []
    for _, row in master.iterrows():
        key = (normalize(row["State"]), normalize(row["District"]))
        data = lookup.get(key)
        if data is None:
            unmatched.append((row["State"], row["District"]))
        for c in out_cols:
            matched[c].append(data[c] if data else None)

    result = master.copy()
    for c in out_cols:
        result[c] = matched[c]

    if unmatched:
        print(f"Warning: {len(unmatched)} (State, District) rows in the main CSV had no "
              f"match in today's IMD PDF. First few: {unmatched[:10]}", file=sys.stderr)

    return result


def main():
    ap = argparse.ArgumentParser(description="Download & merge today's IMD district rainfall data.")
    ap.add_argument("--main-csv", default="master.csv",
                    help="Path to your master CSV with columns: State, District, Lat, Lon")
    ap.add_argument("--out-dir", default="output", help="Directory to write the dated output CSV into")
    ap.add_argument("--keep-pdf", action="store_true", help="Keep the downloaded PDF instead of deleting it")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    pdf_path = os.path.join(args.out_dir, "_imd_rainfall_latest.pdf")

    print(f"Downloading PDF from {PDF_URL} ...")
    download_pdf(PDF_URL, pdf_path)

    print("Parsing PDF ...")
    data_date, rows = parse_pdf(pdf_path)
    print(f"Parsed {len(rows)} rows (data date: {data_date}).")

    print(f"Merging with master CSV: {args.main_csv}")
    result = merge_with_master(args.main_csv, rows)

    out_path = os.path.join(args.out_dir, f"rainfall_{data_date}.csv")
    result.to_csv(out_path, index=False)
    print(f"Wrote: {out_path}")

    if not args.keep_pdf:
        try:
            os.remove(pdf_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()

