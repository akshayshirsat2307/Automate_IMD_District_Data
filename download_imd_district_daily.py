
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urljoin
import re
import unicodedata

import camelot
import pandas as pd
import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ------------------------------------------------------------
# Master CSV
# Must contain:
# State, District, Lat, Lon
# ------------------------------------------------------------

MASTER_CSV = Path("master.csv")


# ============================================================
# IMD URLS
# ============================================================

BASE_URL = "https://mausam.imd.gov.in"

STATE_PDF_URL = (
    BASE_URL
    + "/Rainfall/STATE_RAINFALL_DISTRIBUTION_COUNTRY_INDIA_cd.pdf"
)

DISTRICT_PAGE = (
    "https://mausam.imd.gov.in/"
    "responsive/rainfall_statistics.php?PAGE=4"
)


# ============================================================
# SPECIAL DISTRICT MATCHING
#
# These districts MUST be matched using
# State + District
#
# All other districts will be matched using
# District only.
# ============================================================

SPECIAL_STATE_DISTRICT_MATCHES = {

    (
        "WEST UTTAR PRADESH",
        "HAMIRPUR"
    ),

    (
        "EAST UTTAR PRADESH",
        "BALRAMPUR"
    ),

    (
        "EAST UTTAR PRADESH",
        "PRATAPGARH"
    ),

    (
        "HIMACHAL PRADESH",
        "BILASPUR"
    ),

    (
        "HIMACHAL PRADESH",
        "HAMIRPUR"
    ),

    (
        "EAST RAJASTHAN",
        "PRATAPGARH"
    ),

    (
        "CHHATTISGARH",
        "BALRAMPUR"
    ),

    (
        "CHHATTISGARH",
        "BILASPUR"
    )
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(value):

    if pd.isna(value):
        return ""

    value = str(value)

    # Unicode normalization
    value = unicodedata.normalize(
        "NFKD",
        value
    )

    # Remove hidden characters
    value = value.replace(
        "\u200b",
        ""
    )

    value = value.replace(
        "\ufeff",
        ""
    )

    # Replace non-breaking spaces
    value = value.replace(
        "\xa0",
        " "
    )

    # Uppercase
    value = value.upper().strip()

    # Standardize &
    value = value.replace(
        "&",
        " AND "
    )

    # Remove punctuation
    value = re.sub(
        r"[^A-Z0-9\s]",
        " ",
        value
    )

    # Remove repeated spaces
    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    return value


# ============================================================
# GET PREVIOUS DATE
# ============================================================

prev = datetime.now() - timedelta(days=1)

date_str = prev.strftime(
    "%Y%m%d"
)

date_display = prev.strftime(
    "%Y-%m-%d"
)


print(
    "\nData date:",
    date_display
)


# ============================================================
# 1. DOWNLOAD STATE PDF
# ============================================================

state_pdf_name = (
    f"STATE_RAINFALL_{date_str}.pdf"
)

state_pdf_path = (
    DOWNLOAD_DIR
    / state_pdf_name
)


print(
    "\nDownloading State Rainfall PDF..."
)

response = requests.get(
    STATE_PDF_URL,
    headers={
        "User-Agent": "Mozilla/5.0"
    },
    timeout=120
)

response.raise_for_status()

with open(
    state_pdf_path,
    "wb"
) as f:

    f.write(
        response.content
    )


print(
    "State PDF saved:",
    state_pdf_path
)


# ============================================================
# 2. FIND AND DOWNLOAD DISTRICT PDF
# ============================================================

print(
    "\nFinding latest District Rainfall PDF..."
)

html_response = requests.get(
    DISTRICT_PAGE,
    headers={
        "User-Agent": "Mozilla/5.0"
    },
    timeout=120
)

html_response.raise_for_status()

soup = BeautifulSoup(
    html_response.text,
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
    DISTRICT_PAGE,
    download["href"]
)


print(
    "District PDF URL:",
    pdf_url
)


district_pdf_name = (
    f"IMD_DISTRICT_RAINFALL_{date_str}.pdf"
)

district_pdf_path = (
    DOWNLOAD_DIR
    / district_pdf_name
)


response = requests.get(
    pdf_url,
    headers={
        "User-Agent": "Mozilla/5.0"
    },
    timeout=120
)

response.raise_for_status()

with open(
    district_pdf_path,
    "wb"
) as f:

    f.write(
        response.content
    )


print(
    "District PDF saved:",
    district_pdf_path
)


# ============================================================
# 3. CONVERT DISTRICT PDF TO CSV
# ============================================================

print(
    "\nConverting District PDF to CSV..."
)

tables = camelot.read_pdf(

    str(
        district_pdf_path
    ),

    pages="all",

    flavor="stream"

)


print(
    "Number of extracted tables:",
    len(tables)
)


if len(tables) == 0:

    raise RuntimeError(
        "Camelot did not extract any tables from the PDF."
    )


# Collect all tables
dfs = []

for i, table in enumerate(
    tables
):

    temp_df = table.df.copy()

    print(
        f"Table {i + 1}: "
        f"{temp_df.shape[0]} rows x "
        f"{temp_df.shape[1]} columns"
    )

    dfs.append(
        temp_df
    )


# Combine all tables
converted_df = pd.concat(
    dfs,
    ignore_index=True
)


# Save converted CSV
converted_csv_name = (
    f"IMD_DISTRICT_RAINFALL_{date_str}.csv"
)

converted_csv_path = (
    DOWNLOAD_DIR
    / converted_csv_name
)


converted_df.to_csv(

    converted_csv_path,

    index=False

)


print(
    "\nConverted CSV saved:",
    converted_csv_path
)

print(
    "Converted CSV rows:",
    len(converted_df)
)


# ============================================================
# 4. READ MASTER CSV
# ============================================================

print(
    "\nReading master CSV..."
)

master = pd.read_csv(
    MASTER_CSV,
    dtype=str
)


required_columns = [

    "State",

    "District",

    "Lat",

    "Lon"

]


missing_columns = [

    col

    for col in required_columns

    if col not in master.columns

]


if missing_columns:

    raise ValueError(

        "Master CSV is missing columns: "

        + str(
            missing_columns
        )

    )


print(
    "Master rows:",
    len(master)
)


# ============================================================
# 5. IDENTIFY COLUMN STRUCTURE
# ============================================================

print(
    "\nConverted CSV column count:",
    len(
        converted_df.columns
    )
)

print(
    "Converted CSV columns:"
)

for i, col in enumerate(
    converted_df.columns
):

    print(
        i,
        "->",
        col
    )


# ============================================================
# IMPORTANT:
#
# Camelot with stream flavor often creates columns like:
#
# 0, 1, 2, 3, 4, 5...
#
# We need to identify the district name column.
#
# The following code assumes:
#
# Column 0 = S.No
# Column 1 = State/Subdivision/District name
#
# If your converted CSV has a different structure,
# change NAME_COLUMN below.
# ============================================================

NAME_COLUMN = 1


# ============================================================
# 6. PREPARE CONVERTED CSV
# ============================================================

rainfall = converted_df.copy()


# Convert all values to string
rainfall = rainfall.astype(
    str
)


# Create normalized district/name field
rainfall[
    "Name_Normalized"
] = (

    rainfall[
        NAME_COLUMN
    ]

    .apply(
        normalize_text
    )

)


# ============================================================
# 7. EXTRACT STATE/SUBDIVISION FROM CONVERTED CSV
# ============================================================

# This section attempts to track the State/Subdivision
# from the rows in the converted CSV.
#
# It is useful for the eight special cases.
#
# If the converted CSV contains state names as separate
# heading rows, they will be assigned to following districts.

current_state = ""


# Get normalized special states
special_states = set(

    state

    for state, district

    in SPECIAL_STATE_DISTRICT_MATCHES

)


rainfall[
    "Detected_State"
] = ""


for index in rainfall.index:

    name = rainfall.loc[
        index,
        "Name_Normalized"
    ]

    # If this row looks like one of the known states
    if name in special_states:

        current_state = name

        rainfall.loc[
            index,
            "Detected_State"
        ] = current_state

    else:

        rainfall.loc[
            index,
            "Detected_State"
        ] = current_state


# ============================================================
# 8. PREPARE MASTER NORMALIZED FIELDS
# ============================================================

master[
    "State_Normalized"
] = (

    master[
        "State"
    ]

    .apply(
        normalize_text
    )

)


master[
    "District_Normalized"
] = (

    master[
        "District"
    ]

    .apply(
        normalize_text
    )

)


# ============================================================
# 9. FIND DISTRICT NAME COLUMN
# ============================================================

# The converted CSV name column is NAME_COLUMN.
#
# Create normalized district column.

rainfall[
    "District_Normalized"
] = (

    rainfall[
        NAME_COLUMN
    ]

    .apply(
        normalize_text
    )

)


# ============================================================
# 10. CREATE RESULT
# ============================================================

result = master.copy()


# Columns from converted CSV
# will be appended with prefix "IMD_"

imd_columns = [

    col

    for col in rainfall.columns

    if col not in [

        "Name_Normalized",

        "Detected_State",

        "District_Normalized"

    ]

]


for col in imd_columns:

    result[
        "IMD_" + str(col)
    ] = None


result[
    "Match_Type"
] = "UNMATCHED"


result[
    "Match_Score"
] = None


result[
    "Matched_IMD_District"
] = None


result[
    "Matched_IMD_State"
] = None


# ============================================================
# 11. MATCH MASTER WITH CONVERTED CSV
# ============================================================

print(
    "\nStarting district matching..."
)


for master_index in result.index:

    master_state = (
        result.loc[
            master_index,
            "State_Normalized"
        ]
    )

    master_district = (
        result.loc[
            master_index,
            "District_Normalized"
        ]
    )


    # ========================================================
    # CHECK WHETHER THIS IS ONE OF THE SPECIAL CASES
    # ========================================================

    special_key = (

        master_state,

        master_district

    )


    if special_key in SPECIAL_STATE_DISTRICT_MATCHES:

        # ----------------------------------------------------
        # SPECIAL CASE
        #
        # Match State + District
        # ----------------------------------------------------

        matches = rainfall[

            (
                rainfall[
                    "Detected_State"
                ]
                == master_state
            )

            &

            (
                rainfall[
                    "District_Normalized"
                ]
                == master_district
            )

        ]

        match_type = (
            "STATE_DISTRICT"
        )


    else:

        # ----------------------------------------------------
        # NORMAL CASE
        #
        # Match District ONLY
        # ----------------------------------------------------

        matches = rainfall[

            rainfall[
                "District_Normalized"
            ]

            == master_district

        ]

        match_type = (
            "DISTRICT_ONLY"
        )


    # ========================================================
    # NO MATCH
    # ========================================================

    if len(matches) == 0:

        continue


    # ========================================================
    # MULTIPLE MATCHES
    # ========================================================

    if len(matches) > 1:

        print(
            "\nWARNING: Multiple matches found"
        )

        print(
            "Master State:",
            master_state
        )

        print(
            "Master District:",
            master_district
        )

        print(
            "Number of matches:",
            len(matches)
        )


    # Take first matching record
    matched_row = matches.iloc[0]


    # ========================================================
    # COPY IMD DATA
    # ========================================================

    for col in imd_columns:

        result.loc[

            master_index,

            "IMD_" + str(col)

        ] = matched_row[col]


    # ========================================================
    # MATCH INFORMATION
    # ========================================================

    result.loc[
        master_index,
        "Match_Type"
    ] = match_type


    result.loc[
        master_index,
        "Match_Score"
    ] = 100


    result.loc[
        master_index,
        "Matched_IMD_District"
    ] = matched_row[
        NAME_COLUMN
    ]


    result.loc[
        master_index,
        "Matched_IMD_State"
    ] = matched_row[
        "Detected_State"
    ]


# ============================================================
# 12. SAVE FINAL MASTER CSV
# ============================================================

master_output_name = (

    f"IMD_MASTER_RAINFALL_{date_str}.csv"

)


master_output_path = (

    DOWNLOAD_DIR

    / master_output_name

)


# Remove internal columns
result = result.drop(

    columns=[

        "State_Normalized",

        "District_Normalized"

    ],

    errors="ignore"

)


result.to_csv(

    master_output_path,

    index=False

)


print(
    "\nFinal Master CSV saved:"
)

print(
    master_output_path
)


# ============================================================
# 13. SAVE UNMATCHED RECORDS
# ============================================================

unmatched = result[

    result[
        "Match_Type"
    ]

    == "UNMATCHED"

].copy()


unmatched_output_path = (

    DOWNLOAD_DIR

    / f"IMD_MASTER_UNMATCHED_{date_str}.csv"

)


unmatched.to_csv(

    unmatched_output_path,

    index=False

)


print(
    "\nUnmatched CSV saved:"
)

print(
    unmatched_output_path
)


# ============================================================
# 14. SAVE MATCH SUMMARY
# ============================================================

print(
    "\n======================================"
)

print(
    "MATCH SUMMARY"
)

print(
    "======================================"
)


print(

    result[
        "Match_Type"
    ]

    .value_counts()

)


print(
    "\nTotal Master Records:",
    len(result)
)


print(
    "Matched Records:",
    len(result)
    - len(unmatched)
)


print(
    "Unmatched Records:",
    len(unmatched)
)


# ============================================================
# 15. PRINT UNMATCHED DISTRICTS
# ============================================================

if len(unmatched) > 0:

    print(
        "\nUNMATCHED DISTRICTS:"
    )

    for _, row in unmatched.iterrows():

        print(

            row["State"],

            "|",

            row["District"]

        )


print(
    "\n======================================"
)

print(
    "PROCESS COMPLETED"
)

print(
    "======================================"

)

print(
    "\nGenerated files:"
)

print(
    "1.",
    state_pdf_path
)

print(
    "2.",
    district_pdf_path
)

print(
    "3.",
    converted_csv_path
)

print(
    "4.",
    master_output_path
)

print(
    "5.",
    unmatched_output_path
)
