from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urljoin
import argparse
import re

import camelot
import pandas as pd
import requests
from bs4 import BeautifulSoup
import pdfplumber


# ============================================================
# COMMAND LINE ARGUMENTS
# ============================================================

parser = argparse.ArgumentParser(
    description="Download IMD rainfall PDFs, convert to CSV, and update master CSV."
)

parser.add_argument(
    "--main-csv",
    required=True,
    help="Path to master CSV file"
)

parser.add_argument(
    "--out-dir",
    required=True,
    help="Output folder"
)

args = parser.parse_args()


# ============================================================
# OUTPUT FOLDER
# ============================================================

DOWNLOAD_DIR = Path(
    args.out_dir
)

DOWNLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# MASTER CSV
# ============================================================

MASTER_FILE = Path(
    args.main_csv
)


if not MASTER_FILE.exists():

    raise FileNotFoundError(
        f"Master CSV not found: {MASTER_FILE}"
    )


# ============================================================
# DATE
#
# For daily automation:
# Yesterday's date is used.
#
# Example:
# Today    = 23-07-2026
# Yesterday = 22-07-2026
#
# If you want today's date, change days=1 to days=0.
# ============================================================

prev = datetime.now() - timedelta(
    days=1
)

date_str = prev.strftime(
    "%Y%m%d"
)


print(
    "Processing date:",
    prev.strftime("%d-%m-%Y")
)


# ============================================================
# FILE NAMES
# ============================================================

STATE_PDF_NAME = (
    f"STATE_RAINFALL_{date_str}.pdf"
)

STATE_CSV_NAME = (
    f"STATE_RAINFALL_{date_str}.csv"
)

DISTRICT_PDF_NAME = (
    f"IMD_DISTRICT_RAINFALL_{date_str}.pdf"
)

DISTRICT_CSV_NAME = (
    f"IMD_DISTRICT_RAINFALL_{date_str}.csv"
)

MASTER_OUTPUT_NAME = (
    f"master_updated_{date_str}.csv"
)

UNMATCHED_OUTPUT_NAME = (
    f"master_unmatched_{date_str}.csv"
)


# ============================================================
# FULL PATHS
# ============================================================

STATE_PDF = (
    DOWNLOAD_DIR /
    STATE_PDF_NAME
)

STATE_CSV = (
    DOWNLOAD_DIR /
    STATE_CSV_NAME
)

DISTRICT_PDF = (
    DOWNLOAD_DIR /
    DISTRICT_PDF_NAME
)

DISTRICT_CSV = (
    DOWNLOAD_DIR /
    DISTRICT_CSV_NAME
)

MASTER_OUTPUT = (
    DOWNLOAD_DIR /
    MASTER_OUTPUT_NAME
)

UNMATCHED_OUTPUT = (
    DOWNLOAD_DIR /
    UNMATCHED_OUTPUT_NAME
)


# ============================================================
# PRINT FILE INFORMATION
# ============================================================

print(
    "\n=========================================="
)

print(
    "FILE CONFIGURATION"
)

print(
    "=========================================="
)

print(
    "Master CSV:",
    MASTER_FILE
)

print(
    "Output folder:",
    DOWNLOAD_DIR
)

print(
    "State PDF:",
    STATE_PDF
)

print(
    "State CSV:",
    STATE_CSV
)

print(
    "District PDF:",
    DISTRICT_PDF
)

print(
    "District CSV:",
    DISTRICT_CSV
)

print(
    "Updated Master:",
    MASTER_OUTPUT
)

print(
    "=========================================="
)


# ============================================================
# 1. DOWNLOAD STATE PDF
# ============================================================

print(
    "\nDownloading State Rainfall PDF..."
)


base_url = (
    "https://mausam.imd.gov.in"
)


state_pdf_url = (

    base_url +

    "/Rainfall/"
    "STATE_RAINFALL_DISTRIBUTION_COUNTRY_INDIA_cd.pdf"

)


response = requests.get(
    state_pdf_url,
    timeout=60
)

response.raise_for_status()


with open(
    STATE_PDF,
    "wb"
) as f:

    f.write(
        response.content
    )


print(
    "Downloaded:",
    STATE_PDF
)


# ============================================================
# 2. DOWNLOAD DISTRICT PDF
# ============================================================

print(
    "\nFinding District Rainfall PDF..."
)


PAGE = (
    "https://mausam.imd.gov.in/"
    "responsive/rainfall_statistics.php?PAGE=4"
)


response = requests.get(
    PAGE,
    timeout=60
)

response.raise_for_status()


soup = BeautifulSoup(
    response.text,
    "html.parser"
)


download = soup.find(
    "a",
    id="default-block-btn"
)


if download is None:

    raise RuntimeError(
        "Could not find District PDF download link."
    )


pdf_url = urljoin(
    PAGE,
    download["href"]
)


print(
    "District PDF URL:",
    pdf_url
)


response = requests.get(
    pdf_url,
    timeout=60
)

response.raise_for_status()


with open(
    DISTRICT_PDF,
    "wb"
) as f:

    f.write(
        response.content
    )


print(
    "Downloaded:",
    DISTRICT_PDF
)


# ============================================================
# 3. CONVERT DISTRICT PDF → CSV
# ============================================================

print(
    "\nConverting District PDF to CSV..."
)


tables = camelot.read_pdf(

    str(DISTRICT_PDF),

    pages="all",

    flavor="stream"

)


if len(tables) == 0:

    raise RuntimeError(
        "No tables found in District PDF."
    )


dfs = []


for table_number, table in enumerate(

    tables,

    start=1

):

    temp = table.df.copy()


    print(

        f"District table {table_number}:",

        temp.shape

    )


    dfs.append(
        temp
    )


district_raw = pd.concat(

    dfs,

    ignore_index=True

)


district_raw.to_csv(

    DISTRICT_CSV,

    index=False,

    encoding="utf-8-sig"

)


print(
    "District CSV saved:",
    DISTRICT_CSV
)


print(
    "District CSV rows:",
    len(district_raw)
)


# ============================================================
# 4. CONVERT STATE PDF → CSV
# ============================================================

print(
    "\nConverting State PDF to CSV..."
)


STATE_COLUMNS = [

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
# STATE CSV ROWS
# ============================================================

state_rows = []


# ============================================================
# OPEN STATE PDF
# ============================================================

with pdfplumber.open(

    STATE_PDF

) as pdf:


    total_pages = len(
        pdf.pages
    )


    print(
        "State PDF pages:",
        total_pages
    )


    # ========================================================
    # PROCESS ALL PAGES
    # ========================================================

    for page_number, page in enumerate(

        pdf.pages,

        start=1

    ):


        print(

            f"Processing State PDF page "
            f"{page_number}/{total_pages}"

        )


        tables = (

            page.extract_tables()

        )


        # ====================================================
        # PROCESS TABLES
        # ====================================================

        for table in tables:


            for row in table:


                if not row:

                    continue


                # --------------------------------------------
                # CLEAN CELLS
                # --------------------------------------------

                row = [

                    str(cell).strip()

                    if cell is not None

                    else ""

                    for cell in row

                ]


                # --------------------------------------------
                # SKIP EMPTY ROW
                # --------------------------------------------

                if not any(row):

                    continue


                # --------------------------------------------
                # ONLY KEEP NUMERIC S.NO
                # --------------------------------------------

                if not is_numeric_sno(

                    row[0]

                ):

                    continue


                # --------------------------------------------
                # REQUIRE AT LEAST 10 COLUMNS
                # --------------------------------------------

                if len(row) < 10:

                    print(

                        "Skipping incomplete state row:",

                        row

                    )

                    continue


                # --------------------------------------------
                # KEEP FIRST 10 COLUMNS
                # --------------------------------------------

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


                state_rows.append(

                    clean_row

                )


# ============================================================
# CREATE STATE DATAFRAME
# ============================================================

state_df = pd.DataFrame(

    state_rows,

    columns=STATE_COLUMNS

)


# ============================================================
# REMOVE DUPLICATES
# ============================================================

state_df = state_df.drop_duplicates(

    keep="first"

)


state_df = state_df.reset_index(

    drop=True

)


# ============================================================
# SAVE STATE CSV
# ============================================================

state_df.to_csv(

    STATE_CSV,

    index=False,

    encoding="utf-8-sig"

)


print(

    "State CSV saved:",

    STATE_CSV

)


print(

    "State rows extracted:",

    len(state_df)

)


# ============================================================
# 5. UPDATE MASTER CSV
# ============================================================

print(
    "\n=========================================="
)

print(
    "UPDATING MASTER CSV"
)

print(
    "=========================================="
)


# ============================================================
# READ MASTER
# ============================================================

master = pd.read_csv(

    MASTER_FILE,

    dtype=str

)


# ============================================================
# READ DISTRICT CSV
# ============================================================

imd = pd.read_csv(

    DISTRICT_CSV,

    dtype=str

)


# ============================================================
# CLEAN COLUMN NAMES
# ============================================================

master.columns = (

    master.columns

    .str.strip()

)


imd.columns = (

    imd.columns

    .str.strip()

)


# ============================================================
# NORMALIZE TEXT
# ============================================================

def clean_text(value):

    if pd.isna(value):

        return ""

    value = str(
        value
    ).upper().strip()

    value = re.sub(

        r"\s+",

        " ",

        value

    )

    return value


# ============================================================
# IDENTIFY MASTER DISTRICT COLUMN
# ============================================================

if "DISTRICT" in master.columns:

    MASTER_DISTRICT_COL = "DISTRICT"

elif "District" in master.columns:

    MASTER_DISTRICT_COL = "District"

else:

    raise ValueError(

        "District column not found in master.csv"

    )


# ============================================================
# IDENTIFY MASTER STATE COLUMN
# ============================================================

if (

    "MET.SUBDIVISION/UT/STATE"

    in master.columns

):

    MASTER_STATE_COL = (

        "MET.SUBDIVISION/UT/STATE"

    )

elif "STATE" in master.columns:

    MASTER_STATE_COL = "STATE"

else:

    MASTER_STATE_COL = None


# ============================================================
# IDENTIFY IMD DISTRICT COLUMN
# ============================================================

IMD_DISTRICT_COL = (

    "MET.SUBDIVISION/UT/STATE/DISTRICT"

)


if (

    IMD_DISTRICT_COL

    not in imd.columns

):

    raise ValueError(

        "District column not found in converted District CSV. "

        f"Available columns: {list(imd.columns)}"

    )


# ============================================================
# CLEAN MASTER DISTRICT
# ============================================================

master["_DISTRICT_KEY"] = (

    master[MASTER_DISTRICT_COL]

    .apply(clean_text)

)


# ============================================================
# CLEAN IMD DISTRICT
# ============================================================

imd["_DISTRICT_KEY"] = (

    imd[IMD_DISTRICT_COL]

    .apply(clean_text)

)


# ============================================================
# MASTER STATE
# ============================================================

if MASTER_STATE_COL is not None:

    master["_STATE_KEY"] = (

        master[MASTER_STATE_COL]

        .apply(clean_text)

    )

else:

    master["_STATE_KEY"] = ""


# ============================================================
# RESULT COLUMNS
# ============================================================

RESULT_COLUMNS = [

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
# CREATE / RESET MASTER RESULT COLUMNS
# ============================================================

for col in RESULT_COLUMNS:

    master[col] = ""


# ============================================================
# MATCHING COUNTERS
# ============================================================

matched = 0

unmatched = 0

district_only_matched = 0

state_district_matched = 0


unmatched_rows = []


# ============================================================
# PROCESS MASTER RECORDS
# ============================================================

for master_index, master_row in master.iterrows():


    master_district = (

        master_row["_DISTRICT_KEY"]

    )


    master_state = (

        master_row["_STATE_KEY"]

    )


    # --------------------------------------------------------
    # EMPTY DISTRICT
    # --------------------------------------------------------

    if not master_district:

        unmatched += 1

        continue


    # ========================================================
    # DISTRICT MATCH
    # ========================================================

    candidates = imd[

        imd["_DISTRICT_KEY"]

        ==

        master_district

    ]


    # ========================================================
    # NO MATCH
    # ========================================================

    if len(candidates) == 0:

        unmatched += 1

        unmatched_rows.append({

            "MASTER_STATE":

                master_state,

            "MASTER_DISTRICT":

                master_district,

            "REASON":

                "District not found"

        })

        continue


    # ========================================================
    # EXACTLY ONE DISTRICT
    # ========================================================

    if len(candidates) == 1:

        matched_row = (

            candidates.iloc[0]

        )

        district_only_matched += 1


    # ========================================================
    # MULTIPLE DISTRICTS WITH SAME NAME
    # ========================================================

    else:

        # ----------------------------------------------------
        # Try state + district
        #
        # NOTE:
        # This requires state information in the
        # converted District CSV.
        # ----------------------------------------------------

        if "STATE" in imd.columns:

            imd["_STATE_KEY"] = (

                imd["STATE"]

                .apply(clean_text)

            )


        elif "MET.SUBDIVISION" in imd.columns:

            imd["_STATE_KEY"] = (

                imd["MET.SUBDIVISION"]

                .apply(clean_text)

            )


        else:

            imd["_STATE_KEY"] = ""


        state_candidates = candidates[

            candidates["_STATE_KEY"]

            ==

            master_state

        ]


        if len(state_candidates) == 1:

            matched_row = (

                state_candidates.iloc[0]

            )

            state_district_matched += 1


        else:

            unmatched += 1

            unmatched_rows.append({

                "MASTER_STATE":

                    master_state,

                "MASTER_DISTRICT":

                    master_district,

                "REASON":

                    "Multiple district matches"

            })

            continue


    # ========================================================
    # COPY RAINFALL DATA
    # ========================================================

    for col in RESULT_COLUMNS:


        if col in matched_row.index:


            master.at[

                master_index,

                col

            ] = (

                matched_row[col]

            )


    matched += 1


# ============================================================
# REMOVE TEMPORARY COLUMNS
# ============================================================

master.drop(

    columns=[

        "_DISTRICT_KEY",

        "_STATE_KEY"

    ],

    inplace=True,

    errors="ignore"

)


# ============================================================
# SAVE UPDATED MASTER
# ============================================================

master.to_csv(

    MASTER_OUTPUT,

    index=False,

    encoding="utf-8-sig"

)


# ============================================================
# SAVE UNMATCHED
# ============================================================

if unmatched_rows:


    pd.DataFrame(

        unmatched_rows

    ).to_csv(

        UNMATCHED_OUTPUT,

        index=False,

        encoding="utf-8-sig"

    )


    print(

        "Unmatched records saved:",

        UNMATCHED_OUTPUT

    )


# ============================================================
# FINAL STATUS
# ============================================================

print(
    "\n=========================================="
)

print(
    "IMD DAILY PROCESS COMPLETE"
)

print(
    "=========================================="
)

print(
    "Date:",
    prev.strftime("%d-%m-%Y")
)

print(
    "District PDF:",
    DISTRICT_PDF
)

print(
    "District CSV:",
    DISTRICT_CSV
)

print(
    "State PDF:",
    STATE_PDF
)

print(
    "State CSV:",
    STATE_CSV
)

print(
    "Master records:",
    len(master)
)

print(
    "Matched:",
    matched
)

print(
    "District-only matched:",
    district_only_matched
)

print(
    "State + District matched:",
    state_district_matched
)

print(
    "Unmatched:",
    unmatched
)

print(
    "Updated Master:",
    MASTER_OUTPUT
)

print(
    "=========================================="
)
