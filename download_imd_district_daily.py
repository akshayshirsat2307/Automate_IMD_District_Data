from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urljoin

import camelot
import pandas as pd
import requests
from bs4 import BeautifulSoup

# -------------------------------
# Output folder
# -------------------------------
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# -------------------------------
# State PDF
# -------------------------------
base_url = "https://mausam.imd.gov.in"
state_pdf = base_url + "/Rainfall/STATE_RAINFALL_DISTRIBUTION_COUNTRY_INDIA_cd.pdf"

prev = datetime.now() - timedelta(days=0)

date_str = prev.strftime("%Y%m%d")

state_name = f"STATE_RAINFALL_{date_str}.pdf"

r = requests.get(state_pdf, timeout=60)
r.raise_for_status()

with open(DOWNLOAD_DIR / state_name, "wb") as f:
    f.write(r.content)

print(f"Downloaded {state_name}")

# -------------------------------
# District PDF
# -------------------------------
PAGE = "https://mausam.imd.gov.in/responsive/rainfall_statistics.php?PAGE=4"

html = requests.get(PAGE).text

soup = BeautifulSoup(html, "html.parser")

download = soup.find("a", id="default-block-btn")

pdf_url = urljoin(PAGE, download["href"])



pdf_name = f"IMD_DISTRICT_RAINFALL_{date_str}.pdf"

r = requests.get(pdf_url)

r.raise_for_status()

with open(DOWNLOAD_DIR / pdf_name, "wb") as f:
    f.write(r.content)

print("Downloaded district PDF")

# -------------------------------
# Convert PDF → CSV
# -------------------------------
tables = camelot.read_pdf(
    str(DOWNLOAD_DIR / pdf_name),
    pages="all",
    flavor="stream"
)

dfs = [t.df for t in tables]

df = pd.concat(dfs, ignore_index=True)

csv_name = f"IMD_DISTRICT_RAINFALL_{date_str}.csv"

df.to_csv(DOWNLOAD_DIR / csv_name, index=False)

print("CSV Saved")



from pathlib import Path
from datetime import datetime, timedelta
import pdfplumber
import pandas as pd


# ============================================================
# DOWNLOAD / PROCESSING FOLDER
# ============================================================



# ============================================================
# YESTERDAY'S DATE
#
# Example:
# If today = 23-07-2026
# yesterday = 22-07-2026
#
# Date format:
# YYYYMMDD
# ============================================================

# prev = datetime.now() - timedelta(
#     days=1
# )

# date_str = prev.strftime(
#     "%Y%m%d"
# )


# ============================================================
# DYNAMIC PDF FILE NAME
#
# Example:
# STATE_RAINFALL_20260722.pdf
# ============================================================

pdf_name = (
    f"STATE_RAINFALL_{date_str}.pdf"
)


# Full PDF path

PDF_FILE = (
    DOWNLOAD_DIR /
    pdf_name
)


# ============================================================
# DYNAMIC CSV FILE NAME
#
# Example:
# STATE_RAINFALL_20260722.csv
# ============================================================

csv_name = (
    f"STATE_RAINFALL_{date_str}.csv"
)


# Full CSV path

OUTPUT_CSV = (
    DOWNLOAD_DIR /
    csv_name
)


print(
    "PDF file:",
    PDF_FILE
)

print(
    "CSV file:",
    OUTPUT_CSV
)


# ============================================================
# OUTPUT COLUMNS
# ============================================================

COLUMNS = [

    "S.No",

    "METEOROLOGICAL STATES",

    "DAILY_ACTUAL(mm)",

    "DAILY_NORMAL(mm)",

    "DAILY_%DEP.",

    "DAILY_CAT.",

    "PERIOD_ACTUAL(mm)",

    "PERIOD_NORMAL(mm)",

    "PERIOD_%DEP.",

    "PERIOD_CAT."

]


# ============================================================
# CHECK FIRST COLUMN IS NUMERIC
# ============================================================

def is_numeric_sno(value):

    if value is None:

        return False

    value = str(
        value
    ).strip()

    return value.isdigit()


# ============================================================
# CHECK PDF EXISTS
# ============================================================

if not PDF_FILE.exists():

    raise FileNotFoundError(

        f"PDF not found: {PDF_FILE}"

    )


# ============================================================
# STORE ALL ROWS
# ============================================================

all_rows = []


# ============================================================
# OPEN MULTI-PAGE PDF
# ============================================================

with pdfplumber.open(
    PDF_FILE
) as pdf:


    total_pages = len(
        pdf.pages
    )


    print(
        f"Total pages: {total_pages}"
    )


    # ========================================================
    # PROCESS ALL PAGES
    # ========================================================

    for page_number, page in enumerate(

        pdf.pages,

        start=1

    ):


        print(

            f"Processing page "
            f"{page_number}/{total_pages}"

        )


        # ----------------------------------------------------
        # Extract tables
        # ----------------------------------------------------

        tables = (
            page.extract_tables()
        )


        # ----------------------------------------------------
        # Process every table
        # ----------------------------------------------------

        for table in tables:


            # ------------------------------------------------
            # Process every row
            # ------------------------------------------------

            for row in table:


                if not row:

                    continue


                # ------------------------------------------------
                # Clean cells
                # ------------------------------------------------

                row = [

                    str(cell).strip()
                    if cell is not None
                    else ""

                    for cell in row

                ]


                # ------------------------------------------------
                # Skip blank rows
                # ------------------------------------------------

                if not any(row):

                    continue


                # ------------------------------------------------
                # KEEP ONLY ROWS WHERE FIRST COLUMN IS NUMERIC
                #
                # This removes:
                #
                # REGION : EAST AND NORTH EAST INDIA
                # REGION : NORTH WEST INDIA
                #
                # Repeated headers
                # ------------------------------------------------

                if not is_numeric_sno(

                    row[0]

                ):

                    continue


                # ------------------------------------------------
                # Make sure 10 columns exist
                # ------------------------------------------------

                if len(row) < 10:

                    print(

                        "Skipping incomplete row:",

                        row

                    )

                    continue


                # ------------------------------------------------
                # Select required 10 columns
                # ------------------------------------------------

                clean_row = [

                    row[0],

                    row[1],

                    row[2],

                    row[3],

                    row[4],

                    row[5],

                    row[6],

                    row[7],

                    row[8],

                    row[9]

                ]


                # ------------------------------------------------
                # Add to final list
                # ------------------------------------------------

                all_rows.append(

                    clean_row

                )


# ============================================================
# CREATE DATAFRAME
# ============================================================

df = pd.DataFrame(

    all_rows,

    columns=COLUMNS

)


# ============================================================
# REMOVE DUPLICATES
# ============================================================

df = df.drop_duplicates(

    keep="first"

)


# ============================================================
# RESET INDEX
# ============================================================

df = df.reset_index(

    drop=True

)


# ============================================================
# SAVE CSV
# ============================================================

df.to_csv(

    OUTPUT_CSV,

    index=False,

    encoding="utf-8-sig"

)


# ============================================================
# FINAL STATUS
# ============================================================

print(
    "\n=========================================="
)

print(
    "STATE-WISE RAINFALL PDF → CSV COMPLETE"
)

print(
    "=========================================="
)

print(
    "Date:",
    prev.strftime("%d-%m-%Y")
)

print(
    "Input PDF:",
    PDF_FILE
)

print(
    "Pages processed:",
    total_pages
)

print(
    "State rows extracted:",
    len(df)
)

print(
    "Output CSV:",
    OUTPUT_CSV
)

print(
    "=========================================="
)



#### Convert to master file

import csv, re
import pandas as pd

RAIN_PATH = df
MASTER_PATH = "master.csv"

# ---------- Helpers ----------
def normalize(s):
    if s is None:
        return ""
    s = str(s).upper().strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def parse_row(fields):
    """Return (sno, name, metrics) or None for junk/blank rows."""
    if len(fields) < 2:
        return None
    sno = fields[0].strip()
    rest = list(fields[1:])
    while rest and rest[-1].strip() == '':
        rest.pop()
    if not rest:
        return None
    if rest[0].strip() == '':          # name-position shift
        rest = rest[1:]
    if not rest:
        return None
    name = rest[0].strip()
    metrics = rest[1:]
    return sno, name, metrics

def fix_metrics(metrics, target=8):
    """Remove stray extra blank fields so we always end up with exactly 8 metrics."""
    if len(metrics) == target:
        return metrics, True
    extra = len(metrics) - target
    if extra <= 0:
        return metrics, False
    blanks = [i for i, v in enumerate(metrics) if v.strip() == '']
    if len(blanks) >= extra:
        remove = set(blanks[:extra])
        fixed = [v for i, v in enumerate(metrics) if i not in remove]
        return fixed, len(fixed) == target
    return metrics, False

# subdivision/region labels that own districts directly but are NOT a
# direct/near match to a master state name -> explicit mapping to real state
LEAF_ALIAS_TO_STATE = {
    "GANGETIC WEST BENGAL": "WEST BENGAL",
    "WEST UTTAR PRADESH": "UTTAR PRADESH",
    "EAST UTTAR PRADESH": "UTTAR PRADESH",
    "EAST RAJASTHAN": "RAJASTHAN",
    "WEST RAJASTHAN": "RAJASTHAN",
    "WEST MADHYA PRADESH": "MADHYA PRADESH",
    "EAST MADHYA PRADESH": "MADHYA PRADESH",
    "MADHYA MAHARASHTRA": "MAHARASHTRA",
    "MARATHWADA": "MAHARASHTRA",
    "VIDARBHA": "MAHARASHTRA",
    "RAYALASEEMA": "ANDHRA PRADESH",
    "NORTHERN INTERIOR KARNATAKA": "KARNATAKA",
    "SOUTHERN INTERIOR KARNATAKA": "KARNATAKA",
    "COASTAL KARNATAKA": "KARNATAKA",
}

JUNK_NAMES = {"S.NO", "MET.SUBDIVISION/UT/STATE/DISTRICT", "LEGEND", "1"}  # "1" catches stray col-index header

def load_master():
    m = pd.read_csv(MASTER_PATH)
    m['STATE_N'] = m['State'].apply(normalize)
    m['DISTRICT_N'] = m['District'].apply(normalize)
    return m

def resolve_state(name_norm, master_states):
    """Try to map a header row's name to a real master state name."""
    if name_norm in master_states:
        return name_norm
    stripped = name_norm.replace(" (UT)", "").strip()
    if stripped in master_states:
        return stripped
    if name_norm in LEAF_ALIAS_TO_STATE:
        return LEAF_ALIAS_TO_STATE[name_norm]
    return None

def main():
    master = load_master()
    master_states = set(master['STATE_N'].unique())

    with open(RAIN_PATH, newline='', encoding='utf-8') as f:
        raw_rows = list(csv.reader(f))

    parsed = []
    for r in raw_rows:
        p = parse_row(r)
        if p is None:
            continue
        sno, name, metrics = p
        if not name:
            continue
        if 'DAY:' in name or 'PERIOD' in name:
            continue
        if name.upper() in JUNK_NAMES:
            continue
        parsed.append((sno, name, metrics))

    current_state = None
    out_rows = []
    problems = []

    for sno, name, metrics in parsed:
        name_norm = normalize(name)
        if sno == '':
            # header row: real state (leaf) OR a combined/total row (ignore)
            resolved = resolve_state(name_norm, master_states)
            if resolved:
                current_state = resolved
            # else: combined-total row (e.g. "ASSAM & MEGHALAYA") -> leave current_state unchanged
            continue

        # district row
        if not sno.strip().isdigit():
            continue  # stray junk row (legend text etc.)

        fixed, ok = fix_metrics(metrics)
        if not ok:
            problems.append(("BAD_METRICS", current_state, name, metrics))
            continue

        actual1, normal1, pctdep1, cat1, actual2, normal2, pctdep2, cat2 = fixed
        out_rows.append({
            "S.No": sno,
            "STATE": current_state,
            "DISTRICT": name_norm,
            "DISTRICT_DISPLAY": name.strip(),
            "ACTUAL_1": actual1, "NORMAL_1": normal1, "PCTDEP_1": pctdep1, "CAT_1": cat1,
            "ACTUAL_2": actual2, "NORMAL_2": normal2, "PCTDEP_2": pctdep2, "CAT_2": cat2,
        })

    df = pd.DataFrame(out_rows)

    # Drop verbatim-duplicate district rows (same district name + identical metrics
    # appearing again later in the source, sometimes under a differently-labeled
    # header block - a data artifact, not a real second district)
    dup_key_cols = ['DISTRICT', 'ACTUAL_1', 'NORMAL_1', 'PCTDEP_1', 'CAT_1',
                     'ACTUAL_2', 'NORMAL_2', 'PCTDEP_2', 'CAT_2']
    before = len(df)
    df = df.drop_duplicates(subset=dup_key_cols, keep='first').reset_index(drop=True)
    print(f"Dropped {before - len(df)} verbatim-duplicate rows found in the source file")

    df['STATE_N'] = df['STATE'].apply(normalize)

    # ---------- Match against master (state-scoped exact, then fuzzy) ----------
    import difflib

    def strip_filler(s):
        # remove generic filler words that inflate similarity between unrelated names
        return re.sub(r'\b(DISTRICT|DIST)\b', '', s).strip()

    def match(row, threshold=0.80, root_threshold=0.72):
        cands = master[master['STATE_N'] == row['STATE_N']]
        if cands.empty:
            return pd.Series([None, None, None, "NO_STATE_MATCH"])
        exact = cands[cands['DISTRICT_N'] == row['DISTRICT']]
        if not exact.empty:
            m = exact.iloc[0]
            return pd.Series([m['Lat'], m['Lon'], 1.0, "EXACT"])

        choices = cands['DISTRICT_N'].tolist()
        matches = difflib.get_close_matches(row['DISTRICT'], choices, n=3, cutoff=threshold)
        row_root = strip_filler(row['DISTRICT'])
        for cand_name in matches:
            full_score = difflib.SequenceMatcher(None, row['DISTRICT'], cand_name).ratio()
            root_score = difflib.SequenceMatcher(None, row_root, strip_filler(cand_name)).ratio()
            if root_score >= root_threshold:
                m = cands[cands['DISTRICT_N'] == cand_name].iloc[0]
                return pd.Series([m['Lat'], m['Lon'], round(min(full_score, root_score), 3), "FUZZY"])
        return pd.Series([None, None, None, "NO_MATCH"])

    df[['Lat', 'Lon', 'match_score', 'match_type']] = df.apply(match, axis=1)

    matched = df[df['match_type'].isin(['EXACT', 'FUZZY'])].copy()
    unmatched = df[~df['match_type'].isin(['EXACT', 'FUZZY'])].copy()

    final = matched[[
        'S.No', 'STATE', 'DISTRICT_DISPLAY', 'Lat', 'Lon',
        'ACTUAL_1', 'NORMAL_1', 'PCTDEP_1', 'CAT_1',
        'ACTUAL_2', 'NORMAL_2', 'PCTDEP_2', 'CAT_2', 'match_type', 'match_score'
    ]].rename(columns={'DISTRICT_DISPLAY': 'DISTRICT'})

    final.to_csv("C:/Users/mayur/Downloads/rainfall_matched.csv", index=False)
    unmatched.to_csv("C:/Users/mayur/Downloads/rainfall_unmatched_for_review.csv", index=False)

    print(f"Total district rows parsed: {len(df)}")
    print(f"Matched (exact+fuzzy): {len(matched)}")
    print(f"  - exact: {(df['match_type']=='EXACT').sum()}")
    print(f"  - fuzzy: {(df['match_type']=='FUZZY').sum()}")
    print(f"Unmatched: {len(unmatched)}")
    print(f"Bad-metrics rows skipped: {len(problems)}")
    for p in problems:
        print("  BAD_METRICS:", p)

if __name__ == "__main__":
    main()
