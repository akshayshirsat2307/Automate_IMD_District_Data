# ============================================================
# UPDATE MASTER CSV FROM CONVERTED DISTRICT CSV
# ============================================================

from pathlib import Path
import pandas as pd
import re


# ============================================================
# MASTER CSV
# ============================================================
# -------------------------------
# Output folder
# -------------------------------
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

MASTER_FILE = Path("master.csv")


# ============================================================
# OUTPUT MASTER FILE
# ============================================================

MASTER_OUTPUT = (
    DOWNLOAD_DIR /
    f"master_updated_{date_str}.csv"
)


# ============================================================
# DISTRICT CSV CREATED ABOVE
# ============================================================

DISTRICT_CSV = (
    DOWNLOAD_DIR /
    f"IMD_DISTRICT_RAINFALL_{date_str}.csv"
)


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
# CHECK FILES
# ============================================================

if not MASTER_FILE.exists():

    raise FileNotFoundError(
        f"Master CSV not found: {MASTER_FILE}"
    )


if not DISTRICT_CSV.exists():

    raise FileNotFoundError(
        f"District CSV not found: {DISTRICT_CSV}"
    )


# ============================================================
# READ MASTER
# ============================================================

master = pd.read_csv(

    MASTER_FILE,

    dtype=str

)


# ============================================================
# READ CONVERTED DISTRICT CSV
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
# FUNCTION TO NORMALIZE TEXT
# ============================================================

def clean_text(value):

    if pd.isna(value):

        return ""

    value = str(value).upper().strip()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value


# ============================================================
# IDENTIFY MASTER STATE COLUMN
# ============================================================

if "MET.SUBDIVISION/UT/STATE" in master.columns:

    MASTER_STATE_COL = (
        "MET.SUBDIVISION/UT/STATE"
    )

elif "STATE" in master.columns:

    MASTER_STATE_COL = "STATE"

else:

    MASTER_STATE_COL = None


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
# IDENTIFY IMD DISTRICT COLUMN
# ============================================================

IMD_DISTRICT_COL = (
    "MET.SUBDIVISION/UT/STATE/DISTRICT"
)


if IMD_DISTRICT_COL not in imd.columns:

    raise ValueError(
        "District column not found in converted IMD CSV"
    )


# ============================================================
# CLEAN MASTER DISTRICT
# ============================================================

master["_DISTRICT_KEY"] = (

    master[MASTER_DISTRICT_COL]
    .apply(clean_text)

)


# ============================================================
# CLEAN IMD DISTRICT FIELD
# ============================================================

imd["_FULL_NAME"] = (

    imd[IMD_DISTRICT_COL]
    .apply(clean_text)

)


# ============================================================
# EXTRACT DISTRICT NAME
#
# IMD field can contain:
#
# HAMIRPUR
# EAST UTTAR PRADESH HAMIRPUR
#
# We primarily use the last part as district.
# ============================================================

imd["_DISTRICT_KEY"] = (

    imd["_FULL_NAME"]

)


# ============================================================
# DISTRICTS WHERE STATE + DISTRICT IS REQUIRED
# ============================================================

STATE_DISTRICT_REQUIRED = {

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
# CREATE MASTER STATE KEY
# ============================================================

if MASTER_STATE_COL is not None:

    master["_STATE_KEY"] = (

        master[MASTER_STATE_COL]
        .apply(clean_text)

    )

else:

    master["_STATE_KEY"] = ""


# ============================================================
# EXTRACT STATE FROM IMD
#
# This assumes the IMD district field may be:
#
# HAMIRPUR
#
# or the state/subdivision information is available
# elsewhere.
#
# If your district CSV has a separate state column,
# change this section accordingly.
# ============================================================

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


# ============================================================
# CREATE RESULT COLUMNS
# ============================================================

result_columns = [

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
# CREATE EMPTY COLUMNS IN MASTER
# ============================================================

for col in result_columns:

    master[col] = ""


# ============================================================
# TRACK MATCHING
# ============================================================

matched = 0

unmatched = 0

state_district_matched = 0

district_only_matched = 0


unmatched_rows = []


# ============================================================
# PROCESS MASTER ROWS
# ============================================================

for master_index, master_row in master.iterrows():


    master_district = (

        master_row["_DISTRICT_KEY"]

    )


    master_state = (

        master_row["_STATE_KEY"]

    )


    if not master_district:

        unmatched += 1

        continue


    # ========================================================
    # FIND ALL DISTRICT MATCHES
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
    # ONE DISTRICT MATCH
    # ========================================================

    if len(candidates) == 1:

        matched_row = candidates.iloc[0]

        district_only_matched += 1


    # ========================================================
    # MULTIPLE DISTRICT MATCHES
    # ========================================================

    else:

        # ----------------------------------------------------
        # Try state + district matching
        # ----------------------------------------------------

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

    for col in result_columns:

        if col in matched_row.index:

            master.at[

                master_index,

                col

            ] = matched_row[col]


    matched += 1


# ============================================================
# REMOVE TEMPORARY COLUMNS
# ============================================================

temp_columns = [

    "_DISTRICT_KEY",

    "_STATE_KEY"

]


master.drop(

    columns=temp_columns,

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
# SAVE UNMATCHED RECORDS
# ============================================================

if unmatched_rows:

    unmatched_file = (

        DOWNLOAD_DIR /

        f"master_unmatched_{date_str}.csv"

    )


    pd.DataFrame(

        unmatched_rows

    ).to_csv(

        unmatched_file,

        index=False,

        encoding="utf-8-sig"

    )


    print(

        "Unmatched file:",

        unmatched_file

    )


# ============================================================
# FINAL REPORT
# ============================================================

print(

    "\n=========================================="

)

print(

    "MASTER CSV UPDATE COMPLETE"

)

print(

    "=========================================="

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
