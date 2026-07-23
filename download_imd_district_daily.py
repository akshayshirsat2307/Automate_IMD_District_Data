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
