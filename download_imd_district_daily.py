

#!/usr/bin/env python3

"""
IMD District Rainfall Downloader -> PDF -> Converted CSV -> Master CSV

Workflow
--------
1. Download latest IMD District Rainfall Distribution PDF
2. Save the original PDF
3. Extract district-level rainfall data from ALL PDF pages
4. Save extracted data as converted CSV
5. Match State + District with master CSV
6. Use exact normalized matching first
7. Use fuzzy matching for remaining unmatched districts
8. Save final master CSV with rainfall data
9. Save unmatched records for quality checking

Required master CSV columns:
    State
    District
    Lat
    Lon

Install:
    pip install requests pdfplumber pandas rapidfuzz

Run:
    python imd_rainfall_update.py \
        --main-csv master.csv \
        --out-dir output
"""

import argparse
import os
import re
import sys
from datetime import datetime

import pandas as pd
import requests
import pdfplumber

try:
    from rapidfuzz import process, fuzz
except ImportError:
    print("Please install rapidfuzz:")
    print("pip install rapidfuzz")
    sys.exit(1)


# ============================================================
# CONFIGURATION
# ============================================================

PDF_URL = (
    "https://mausam.imd.gov.in/Rainfall/"
    "DISTRICT_RAINFALL_DISTRIBUTION_COUNTRY_INDIA_cd.pdf"
)

FUZZY_THRESHOLD = 85


# ============================================================
# DOWNLOAD PDF
# ============================================================

def download_pdf(url, output_path):

    print("\nDownloading IMD PDF...")
    print(url)

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=120
    )

    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    print("PDF saved:")
    print(output_path)

    return output_path


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(value):

    if pd.isna(value):
        return ""

    value = str(value).upper().strip()

    # Replace & with AND
    value = value.replace("&", " AND ")

    # Common abbreviations
    replacements = {
        "DIST.": "DISTRICT",
        "DIST": "DISTRICT",
        "DISTS": "DISTRICTS",
        "ST.": "SAINT",
        "ST ": "SAINT ",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    # Remove punctuation
    value = re.sub(r"[^A-Z0-9\s]", " ", value)

    # Remove repeated spaces
    value = re.sub(r"\s+", " ", value).strip()

    return value


# ============================================================
# EXTRACT DATE
# ============================================================

def extract_data_date(text):

    patterns = [
        r"DAY\s*:\s*(\d{2})-(\d{2})-(\d{4})",
        r"DAY\s*:\s*(\d{2})/(\d{2})/(\d{4})",
        r"DATE\s*:\s*(\d{2})-(\d{2})-(\d{4})",
        r"DATE\s*:\s*(\d{2})/(\d{2})/(\d{4})",
    ]

    for pattern in patterns:

        match = re.search(pattern, text, re.IGNORECASE)

        if match:

            dd, mm, yyyy = match.groups()

            return f"{yyyy}-{mm}-{dd}"

    return datetime.now().strftime("%Y-%m-%d")


# ============================================================
# NUMBER CHECK
# ============================================================

def is_number(value):

    if value == "ND":
        return True

    try:
        float(value)
        return True
    except:
        return False


# ============================================================
# CONVERT NUMBER
# ============================================================

def convert_number(value):

    if value is None:
        return None

    if str(value).upper() == "ND":
        return None

    try:
        return float(value)
    except:
        return None


# ============================================================
# PARSE RAINFALL BLOCK
# ============================================================

def parse_block(values, index):

    if index >= len(values):
        raise IndexError

    actual = values[index]
    index += 1

    if index >= len(values):
        raise IndexError

    normal = values[index]
    index += 1

    # When Normal is ND,
    # IMD does not provide departure/category
    if normal == "ND":

        return {
            "Actual": convert_number(actual),
            "Normal": None,
            "Dept": None,
            "Category": None
        }, index

    if index + 1 >= len(values):
        raise IndexError

    dept = values[index]
    index += 1

    category = values[index]
    index += 1

    return {
        "Actual": convert_number(actual),
        "Normal": convert_number(normal),
        "Dept": convert_number(dept),
        "Category": category
    }, index


# ============================================================
# FIND NAME + NUMERIC DATA
# ============================================================

def split_name_and_values(line):

    tokens = line.split()

    for i, token in enumerate(tokens):

        if is_number(token):

            name = " ".join(tokens[:i]).strip()

            if name:

                return name, tokens[i:]

    return None, None


# ============================================================
# PARSE PDF
# ============================================================

def parse_pdf(pdf_path):

    rows = []

    current_state = None
    data_date = None

    print("\nReading PDF...")

    with pdfplumber.open(pdf_path) as pdf:

        print("Total pages:", len(pdf.pages))

        for page_number, page in enumerate(pdf.pages, start=1):

            print(
                f"Processing page {page_number}/{len(pdf.pages)}"
            )

            text = page.extract_text(
                x_tolerance=2,
                y_tolerance=3
            ) or ""

            if not text:
                continue

            if data_date is None:

                data_date = extract_data_date(text)

            lines = text.split("\n")

            for raw_line in lines:

                line = raw_line.strip()

                if not line:
                    continue

                # Skip common headers
                skip_words = [
                    "INDIA METEOROLOGICAL DEPARTMENT",
                    "HYDROMET DIVISION",
                    "DISTRICT RAINFALL DISTRIBUTION",
                    "DAY:",
                    "S.NO",
                    "LEGEND",
                    "CATEGORY",
                    "NOTE :",
                    "LARGE EXCESS",
                    "EXCESS",
                    "NORMAL",
                    "DEFICIENT",
                    "LARGE DEFICIENT",
                    "NO RAIN",
                    "NOT AVAILABLE"
                ]

                if any(
                    line.upper().startswith(word)
                    for word in skip_words
                ):
                    continue

                # ==================================================
                # DISTRICT ROW
                # ==================================================

                match = re.match(
                    r"^(\d+)\s+(.*)$",
                    line
                )

                if match:

                    serial_number = match.group(1)

                    rest = match.group(2)

                    name, values = (
                        split_name_and_values(rest)
                    )

                    if not name:
                        continue

                    if not values:
                        continue

                    try:

                        daily, index = parse_block(
                            values,
                            0
                        )

                        cumulative, _ = parse_block(
                            values,
                            index
                        )

                    except Exception:

                        continue

                    if current_state is None:
                        current_state = ""

                    rows.append({

                        "State":
                            current_state,

                        "District":
                            name,

                        "Actual":
                            daily["Actual"],

                        "Normal":
                            daily["Normal"],

                        "Dept":
                            daily["Dept"],

                        "Category":
                            daily["Category"],

                        "Cumulative_Actual":
                            cumulative["Actual"],

                        "Cumulative_Normal":
                            cumulative["Normal"],

                        "Cumulative_Dept":
                            cumulative["Dept"],

                        "Cumulative_Category":
                            cumulative["Category"],

                        "Source_Page":
                            page_number,

                        "SNo":
                            serial_number,

                        "Data_Date":
                            data_date

                    })

                    continue

                # ==================================================
                # STATE ROW
                # ==================================================

                name, values = (
                    split_name_and_values(line)
                )

                if not name:
                    continue

                if not values:
                    continue

                try:

                    daily, index = parse_block(
                        values,
                        0
                    )

                    cumulative, _ = parse_block(
                        values,
                        index
                    )

                except Exception:

                    continue

                # A line with rainfall values and no S.No
                # is treated as a state/subdivision heading

                current_state = name

    df = pd.DataFrame(rows)

    if df.empty:

        raise RuntimeError(
            "No district rainfall data was extracted from PDF."
        )

    # Remove possible duplicate records
    df = df.drop_duplicates(
        subset=[
            "State",
            "District"
        ],
        keep="last"
    )

    print(
        f"\nExtracted {len(df)} records from PDF."
    )

    return data_date, df


# ============================================================
# CREATE STATE + DISTRICT KEY
# ============================================================

def create_key(state, district):

    return (
        normalize_text(state)
        + "|||"
        + normalize_text(district)
    )


# ============================================================
# FUZZY MATCH
# ============================================================

def fuzzy_match(
    master_state,
    master_district,
    converted_df
):

    state_norm = normalize_text(
        master_state
    )

    district_norm = normalize_text(
        master_district
    )

    # First restrict to same state
    state_rows = converted_df[
        converted_df["_State_Normalized"]
        == state_norm
    ]

    if state_rows.empty:

        return None, 0

    choices = (
        state_rows["_District_Normalized"]
        .dropna()
        .unique()
        .tolist()
    )

    if not choices:

        return None, 0

    result = process.extractOne(
        district_norm,
        choices,
        scorer=fuzz.token_sort_ratio
    )

    if result is None:

        return None, 0

    matched_name = result[0]

    score = result[1]

    if score >= FUZZY_THRESHOLD:

        return matched_name, score

    return None, score


# ============================================================
# MERGE WITH MASTER
# ============================================================

def merge_with_master(
    master_csv,
    converted_csv,
    output_csv,
    unmatched_csv
):

    print("\nReading master CSV...")

    master = pd.read_csv(
        master_csv,
        dtype=str
    )

    print(
        "Master records:",
        len(master)
    )

    required_columns = [
        "State",
        "District",
        "Lat",
        "Lon"
    ]

    missing = [
        col
        for col in required_columns
        if col not in master.columns
    ]

    if missing:

        raise ValueError(
            f"Master CSV missing columns: {missing}"
        )

    print("\nReading converted CSV...")

    rainfall = pd.read_csv(
        converted_csv,
        dtype=str
    )

    print(
        "Converted rainfall records:",
        len(rainfall)
    )

    # Normalize fields
    master["_State_Normalized"] = (
        master["State"]
        .apply(normalize_text)
    )

    master["_District_Normalized"] = (
        master["District"]
        .apply(normalize_text)
    )

    rainfall["_State_Normalized"] = (
        rainfall["State"]
        .apply(normalize_text)
    )

    rainfall["_District_Normalized"] = (
        rainfall["District"]
        .apply(normalize_text)
    )

    # ========================================================
    # EXACT MATCH
    # ========================================================

    rainfall["Match_Key"] = (
        rainfall["_State_Normalized"]
        + "|||"
        + rainfall["_District_Normalized"]
    )

    master["Match_Key"] = (
        master["_State_Normalized"]
        + "|||"
        + master["_District_Normalized"]
    )

    # Remove duplicate rainfall keys
    rainfall_lookup = (
        rainfall
        .drop_duplicates(
            subset=["Match_Key"],
            keep="last"
        )
        .set_index("Match_Key")
    )

    rainfall_columns = [

        "Actual",
        "Normal",
        "Dept",
        "Category",

        "Cumulative_Actual",
        "Cumulative_Normal",
        "Cumulative_Dept",
        "Cumulative_Category",

        "Source_Page",
        "SNo",
        "Data_Date"

    ]

    # ========================================================
    # EXACT MERGE
    # ========================================================

    result = master.copy()

    for column in rainfall_columns:

        if column in rainfall_lookup.columns:

            result[column] = (
                result["Match_Key"]
                .map(
                    rainfall_lookup[column]
                )
            )

        else:

            result[column] = None

    result["Match_Type"] = ""

    result["Match_Score"] = None

    exact_mask = (
        result["Actual"].notna()
        | result["Normal"].notna()
        | result["Category"].notna()
    )

    result.loc[
        exact_mask,
        "Match_Type"
    ] = "EXACT"

    result.loc[
        exact_mask,
        "Match_Score"
    ] = 100

    # ========================================================
    # FUZZY MATCH UNMATCHED
    # ========================================================

    unmatched_indices = result[
        ~exact_mask
    ].index

    print(
        "\nExact matches:",
        exact_mask.sum()
    )

    print(
        "Unmatched before fuzzy matching:",
        len(unmatched_indices)
    )

    for index in unmatched_indices:

        master_state = result.loc[
            index,
            "State"
        ]

        master_district = result.loc[
            index,
            "District"
        ]

        matched_district, score = fuzzy_match(

            master_state,

            master_district,

            rainfall

        )

        if matched_district is None:

            continue

        state_norm = normalize_text(
            master_state
        )

        match_rows = rainfall[
            (
                rainfall["_State_Normalized"]
                == state_norm
            )
            &
            (
                rainfall["_District_Normalized"]
                == matched_district
            )
        ]

        if match_rows.empty:

            continue

        matched_row = match_rows.iloc[0]

        for column in rainfall_columns:

            if column in matched_row:

                result.loc[
                    index,
                    column
                ] = matched_row[column]

        result.loc[
            index,
            "Match_Type"
        ] = "FUZZY"

        result.loc[
            index,
            "Match_Score"
        ] = round(
            score,
            2
        )

    # ========================================================
    # FINAL STATUS
    # ========================================================

    final_matched = (
        result["Match_Type"]
        != ""
    )

    result.loc[
        ~final_matched,
        "Match_Type"
    ] = "UNMATCHED"

    # ========================================================
    # REMOVE INTERNAL COLUMNS
    # ========================================================

    internal_columns = [

        "_State_Normalized",
        "_District_Normalized",
        "Match_Key"

    ]

    result = result.drop(
        columns=internal_columns,
        errors="ignore"
    )

    # ========================================================
    # SAVE FINAL MASTER
    # ========================================================

    result.to_csv(
        output_csv,
        index=False
    )

    print(
        "\nFinal master CSV saved:"
    )

    print(
        output_csv
    )

    print(
        "\nMatch summary:"
    )

    print(
        result["Match_Type"]
        .value_counts()
    )

    # ========================================================
    # SAVE UNMATCHED
    # ========================================================

    unmatched = result[
        result["Match_Type"]
        == "UNMATCHED"
    ].copy()

    unmatched.to_csv(
        unmatched_csv,
        index=False
    )

    print(
        "\nUnmatched CSV saved:"
    )

    print(
        unmatched_csv
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--main-csv",
        required=True,
        help="Master CSV containing State, District, Lat, Lon"
    )

    parser.add_argument(
        "--out-dir",
        default="output",
        help="Output directory"
    )

    args = parser.parse_args()

    os.makedirs(
        args.out_dir,
        exist_ok=True
    )

    # ========================================================
    # STEP 1: TEMP PDF
    # ========================================================

    temp_pdf = os.path.join(
        args.out_dir,
        "imd_rainfall_latest.pdf"
    )

    # ========================================================
    # STEP 2: DOWNLOAD PDF
    # ========================================================

    download_pdf(
        PDF_URL,
        temp_pdf
    )

    # ========================================================
    # STEP 3: PARSE PDF
    # ========================================================

    data_date, rainfall_df = parse_pdf(
        temp_pdf
    )

    print(
        "\nIMD data date:",
        data_date
    )

    # ========================================================
    # STEP 4: SAVE CONVERTED CSV
    # ========================================================

    converted_csv = os.path.join(

        args.out_dir,

        f"IMD_Rainfall_Converted_{data_date}.csv"

    )

    rainfall_df.to_csv(
        converted_csv,
        index=False
    )

    print(
        "\nConverted CSV saved:"
    )

    print(
        converted_csv
    )

    # ========================================================
    # STEP 5: FINAL MASTER CSV
    # ========================================================

    master_output = os.path.join(

        args.out_dir,

        f"IMD_Rainfall_Master_{data_date}.csv"

    )

    # ========================================================
    # STEP 6: UNMATCHED CSV
    # ========================================================

    unmatched_output = os.path.join(

        args.out_dir,

        f"IMD_Rainfall_Unmatched_{data_date}.csv"

    )

    # ========================================================
    # STEP 7: MERGE
    # ========================================================

    merge_with_master(

        master_csv=args.main_csv,

        converted_csv=converted_csv,

        output_csv=master_output,

        unmatched_csv=unmatched_output

    )

    print(
        "\n======================================"
    )

    print(
        "PROCESS COMPLETED SUCCESSFULLY"
    )

    print(
        "======================================"
    )

    print(
        "\nFiles created:"
    )

    print(
        "1. PDF:"
    )

    print(
        temp_pdf
    )

    print(
        "\n2. Converted CSV:"
    )

    print(
        converted_csv
    )

    print(
        "\n3. Final Master CSV:"
    )

    print(
        master_output
    )

    print(
        "\n4. Unmatched CSV:"
    )

    print(
        unmatched_output
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
