import pandas as pd
import re
from datetime import datetime

# Known boolean/status value groups that should be consistent — flag if mixed
BOOLEAN_VALUE_GROUPS = [
    {'yes', 'no'},
    {'y', 'n'},
    {'true', 'false'},
    {'paid', 'unpaid'},
    {'active', 'inactive'},
]

def normalize_amount_str(s: str) -> str:
    # Remove spaces used as thousand separators e.g. "7 200" -> "7200"
    s = re.sub(r'(\d)\s+(\d)', r'\1\2', s)
    # Remove all non-numeric chars except dot and minus
    s = re.sub(r'[^\d.-]', '', s)
    # Collapse multiple dots
    s = re.sub(r'\.(?=.*\.)', '', s)
    return s

# Function to detect if two or more original columns were mapped to the same standard field name.
# This is a real bug source: after rename_columns, the dataframe would end up with two columns
# sharing one name, and every df.at[idx, col] lookup downstream returns a Series instead of a
# single value, causing "truth value of a Series is ambiguous" crashes deep inside cleaning.
# Returns a dict of {mapped_to: [original_col1, original_col2, ...]} for every collision found.
def detect_duplicate_mappings(mapping: dict) -> dict:
    seen = {}
    for original_col, info in mapping.items():
        if not isinstance(info, dict):
            continue
        mapped_to = str(info.get("mapped_to", "")).strip()
        # "unknown" is allowed to repeat — those columns are never renamed, so they never collide
        if mapped_to in ("", "unknown"):
            continue
        seen.setdefault(mapped_to, []).append(original_col)
    return {standard_name: cols for standard_name, cols in seen.items() if len(cols) > 1}

# Main function to clean the dataframe based on the confirmed mapping
def clean_dataframe(df: pd.DataFrame, mapping: dict, fill_rates: dict = None) -> tuple:
    """
    Main cleaning function, takes a raw dataframe and confirmed column mapping.
    Mapping structure: {original_col: {"mapped_to": "amount", "field_type": "numeric"}}
    fill_rates: {original_col: float} — proportion of non-empty values per column (0.0 to 1.0).
    Columns with fill rate below 50% get one summary flag instead of per-row missing value flags.
    Returns cleaned dataframe and a validation report.

    Raises ValueError early if the mapping has two original columns mapped to the same
    standard field name — this would otherwise create duplicate column names after renaming
    and crash deep inside cleaning with a confusing pandas error. Catching it here gives a
    clear, actionable message pointing at the actual problem instead.
    """
    duplicates = detect_duplicate_mappings(mapping)
    if duplicates:
        details = "; ".join(
            f"'{standard_name}' is claimed by columns {cols}"
            for standard_name, cols in duplicates.items()
        )
        raise ValueError(
            f"Mapping conflict: two or more original columns are mapped to the same field. {details}. "
            f"Please go back to the mapping step and give each column a unique 'Mapped To' value."
        )

    if fill_rates is None:
        fill_rates = {}

    # Keep a copy of original dataframe for comparison
    original_df = df.copy()

    # Track all issues found
    issues = []

    #Rename columns using confirmed mapping.Must happen first so cleaning functions can find columns by standard names
    df = rename_columns(df, mapping)
    # Clean date columns
    df = clean_dates(df, mapping, issues)
    # Check logical order of dates (e.g. End Date should not be before Start Date)
    check_date_order(df, mapping, issues)
    # Clean amount columns
    df = clean_amounts(df, mapping, issues)
    # Standardize text column casing
    df = standardize_casing(df, mapping, issues)
    # Handle null values — pass fill_rates so sparse columns get a summary flag instead of per-row noise
    df = handle_nulls(df, mapping, issues, fill_rates)
    # Check text columns for inconsistent boolean/status values
    check_value_consistency(df, mapping, issues)
    # Handle duplicates
    df = handle_duplicates(df, mapping, issues)
    # Build the validation report
    report = build_validation_report(df, original_df, issues)
    return df, report

# Function to rename columns based on the confirmed mapping
def rename_columns(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Rename original columns to their mapped standard names.Extracts mapped_to from the new mapping structure.
    Must be called before any cleaning step so cleaning functions. Can find columns by their standard names.
    Columns mapped to "unknown" are skipped and kept under their original name.
    This prevents multiple unknown columns from colliding into one duplicate "unknown" column.
    """
    # Build a rename dictionary from the new mapping structure.{original_col: mapped_to}
    # Skip "unknown" mappings so each unmapped column keeps its own unique original name
    rename_dict = {
        original_col: info["mapped_to"].strip()
        for original_col, info in mapping.items()
        if isinstance(info, dict) and "mapped_to" in info and info["mapped_to"].strip() != "unknown"
    }
    df = df.rename(columns=rename_dict)
    return df

# Function to clean and standardize date columns
def clean_dates(df: pd.DataFrame, mapping: dict, issues: list) -> pd.DataFrame:
    """
    Find all columns with field_type 'date' using the confirmed mapping.Standardizes all date values to YYYY-MM-DD format.
    Uses DD/MM/YYYY as the standard input format.Flags any dates that cannot be parsed for auditor review.
    Skips columns mapped to "unknown" since those were not renamed and have no standard meaning yet.
    """
    # Find all columns whose field_type is date using the mapping. Look at mapped_to names because columns were already renamed.
    # Skip "unknown" mapped_to since those columns were left under their original name and have no confirmed field_type
    date_columns = [
        info["mapped_to"]
        for info in mapping.values()
        if isinstance(info, dict) and info.get("field_type") == "date"
        and info.get("mapped_to") != "unknown"
        and info.get("mapped_to") in df.columns
    ]
    for col in date_columns:
        for idx, value in df[col].items():
            # Skip empty values.
            if pd.isna(value) or str(value).strip() == "":
                continue
            original_value = value
            cleaned = None            
            try:
                # To avoid UserWarning when format is already ISO (YYYY-MM-DD),
                # only use dayfirst=True for potentially ambiguous strings.
                val_str = str(value).strip()
                dayfirst = not (len(val_str) >= 10 and val_str[4] == '-' and val_str[7] == '-')
                dt = pd.to_datetime(val_str, dayfirst=dayfirst, errors='coerce')
                if pd.notna(dt) and dt.year >= 1900:
                    cleaned = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

            if cleaned:
                # Successfully parsed, replace with standardized date
                df.at[idx, col] = cleaned
            else:
                # Could not parse or year missing, flag for auditor
                df.at[idx, col] = original_value
                issues.append({
                    "row": int(idx) + 2,
                    "column": col,
                    "row_index": idx,
                    "original_value": str(original_value),
                    "issue": f"Invalid date '{original_value}' — check this cell and correct it to DD/MM/YYYY format (e.g. 15/03/2024)",
                    "severity": "high"
                })
    return df

# Function to clean and standardize amount columns
def clean_amounts(df: pd.DataFrame, mapping: dict, issues: list) -> pd.DataFrame:
    """
    Find all columns with field_type 'numeric' using the confirmed mapping.Standardizes values to float numbers.
    Removes commas, currency symbols and whitespace.Converts accounting negatives e.g.(1,500) to -1500.0.
    Flags values that cannot be converted to a number.
    Skips columns mapped to "unknown" since those were not renamed and have no standard meaning yet.
    """
    # Find all columns whose field_type is numeric using the mapping. Look at mapped_to names because columns were already renamed.
    # Skip "unknown" mapped_to since those columns were left under their original name and have no confirmed field_type
    amount_columns = [
        info["mapped_to"]
        for info in mapping.values()
        if isinstance(info, dict) and info.get("field_type") == "numeric"
        and info.get("mapped_to") != "unknown"
        and info.get("mapped_to") in df.columns
    ]
    for col in amount_columns:
        for idx, value in df[col].items():
            # Skip empty values.
            if pd.isna(value) or str(value).strip() == "":
                continue
            original_value = value
            # If already a number no cleaning needed, convert to float
            if isinstance(value, (int, float)):
                df.at[idx, col] = float(value)
                continue
            cleaned_str = str(value).strip()
            # Check for accounting negative notation e.g. (1,500)
            is_negative = cleaned_str.startswith("(") and cleaned_str.endswith(")")
            cleaned_str = cleaned_str.strip("()")
            cleaned_str = normalize_amount_str(cleaned_str)

            # Try converting to float
            try:
                amount = float(cleaned_str)
                # Apply negative if value was in brackets
                if is_negative:
                    amount = -amount
                df.at[idx, col] = amount
            except ValueError:
                # Could not convert, flag for auditor
                df.at[idx, col] = original_value
                issues.append({
                    "row": int(idx) + 2,
                    "column": col,
                    "row_index": idx,
                    "original_value": str(original_value),
                    "issue": f"'{original_value}' is not a valid number, correct or remove this value",
                    "severity": "high"
                })
    return df

# Function to standardize text column casing 
def standardize_casing(df: pd.DataFrame, mapping: dict, issues: list) -> pd.DataFrame:
    """
    Find all columns with field_type 'title' using confirmed mapping.
    Standardizes all text values to Title Case.
    Skips empty values and numeric-looking values.
    Skips columns mapped to "unknown" since those were not renamed and have no standard meaning yet.
    """
    # Find all columns whose field_type is text using the mapping.
    # Skip "unknown" mapped_to since those columns were left under their original name and have no confirmed field_type
    text_columns = [
        info["mapped_to"]
        for info in mapping.values()
        if isinstance(info, dict) and info.get("field_type") == "text"
        and info.get("mapped_to") != "unknown"
        and info.get("mapped_to") in df.columns
    ]
    # Loop through text columns and standardize to title case, skipping empty and numeric values
    for col in text_columns:
        for idx, value in df[col].items():
            # Skip empty values
            if pd.isna(value) or str(value).strip() == "":
                continue
            # Skip if value is already a number
            if isinstance(value, (int, float)):
                continue
            # Convert to title case
            df.at[idx, col] = str(value).strip().title()
    return df

# Function to check text columns for inconsistent boolean/status values
def check_value_consistency(df: pd.DataFrame, mapping: dict, issues: list) -> None:
    text_columns = [
        info["mapped_to"].strip()
        for info in mapping.values()
        if isinstance(info, dict) and info.get("field_type") == "text"
        and info.get("mapped_to", "").strip() not in ("", "unknown")
        and info.get("mapped_to", "").strip() in df.columns
    ]
    for col in text_columns:
        unique_vals = set(
            str(v).strip().lower()
            for v in df[col].dropna()
            if str(v).strip() != ""
        )
        for group in BOOLEAN_VALUE_GROUPS:
            found = unique_vals & group
            if len(found) > 1:
                issues.append({
                    "row": "N/A",
                    "column": col,
                    "row_index": "N/A",
                    "original_value": str(found),
                    "issue": f"Mixed values in '{col}': {sorted(found)} — this column has inconsistent entries. Standardise to one format throughout (e.g. use 'Yes' everywhere, not a mix of 'Yes' and 'Y')",
                    "severity": "medium"
                })
                break

# Function to check if any date column appears out of order relative to another date column in the same row
def check_date_order(df: pd.DataFrame, mapping: dict, issues: list) -> None:
    date_cols = [
        info["mapped_to"].strip()
        for info in mapping.values()
        if isinstance(info, dict) and info.get("field_type") == "date"
        and info.get("mapped_to", "").strip() not in ("", "unknown")
        and info.get("mapped_to", "").strip() in df.columns
    ]
    if len(date_cols) < 2:
        return
    for idx in df.index:
        parsed = []
        for col in date_cols:
            try:
                val_str = str(df.at[idx, col]).strip()
                if val_str == "" or val_str.lower() == "nan":
                    continue
                # Avoid UserWarning for ISO strings and handle NaT to prevent 500 error
                dayfirst = not (len(val_str) >= 10 and val_str[4] == '-' and val_str[7] == '-')
                dt = pd.to_datetime(val_str, dayfirst=dayfirst, errors='coerce')
                if pd.notna(dt):
                    parsed.append((col, dt))
            except Exception:
                pass
        # Flag any pair where the second date is before the first by more than 1 day to avoid same-day false positives
        for i in range(len(parsed) - 1):
            col_a, date_a = parsed[i]
            col_b, date_b = parsed[i + 1]
            if (date_a - date_b).days > 1:
                issues.append({
                    "row": int(idx) + 2,
                    "column": col_b,
                    "row_index": idx,
                    "original_value": str(df.at[idx, col_b]),
                    "issue": f"Date order issue — '{col_b}' ({df.at[idx, col_b]}) falls before '{col_a}' ({df.at[idx, col_a]}), which is unexpected. Check whether the dates in this row were entered correctly.",
                    "severity": "medium"
                })

# Function to handle null values
def handle_nulls(df: pd.DataFrame, mapping: dict, issues: list, fill_rates: dict = None) -> pd.DataFrame:
    """
    Flags two types of issues:
    1. Missing values in confirmed mapped columns — with fill-rate-aware logic:
       - Fill rate < 50%: flag ONCE with the fill rate percentage (per-row flags would be noise)
       - Fill rate >= 50%: flag per-row so each missing value gets auditor attention
    2. Unknown columns, flagged once per column, never per row. Includes fill rate summary if available.
    Does not drop or fill any values, auditor decides.
    """
    if fill_rates is None:
        fill_rates = {}

    # Flag unknown columns once, not per row. Use original_col since unknown columns were never renamed
    for original_col, info in mapping.items():
        if isinstance(info, dict) and info.get("mapped_to") == "unknown":
            reviewed_unknown = bool(info.get("reviewed_unknown"))
            rate = fill_rates.get(original_col)
            # Build a clear message for the auditor based on why the column is unknown and its fill rate
            if rate is not None:
                fill_pct = round(rate * 100)
                missing_pct = 100 - fill_pct
                fill_note = f" {missing_pct}% of its values are empty."
            else:
                fill_note = ""
            if reviewed_unknown:
                base_msg = (
                    f"Column '{original_col}' was left as unknown after review."
                    f"{fill_note}"
                    f" No checks were run on this column — review it carefully and confirm whether it contains relevant data."
                )
            else:
                base_msg = (
                    f"Column '{original_col}' could not be identified."
                    f"{fill_note}"
                    f" This column was excluded from all checks — review it carefully to confirm what it represents."
                )
            issues.append({
                "row": "N/A",
                "column": original_col,
                "row_index": "N/A",
                "original_value": "N/A",
                "issue": base_msg,
                "severity": "info" if reviewed_unknown else "medium"
            })

    # Flag missing values in confirmed columns using fill-rate-aware logic:
    # - Sparse columns (fill rate < 50%) → one summary flag, no per-row noise
    # - Normal columns (fill rate >= 50%) → per-row flags so each gap gets auditor attention
    # Skip unknown mapped_to since those are already handled above
    confirmed_columns = [
        (original_col, info["mapped_to"])
        for original_col, info in mapping.items()
        if isinstance(info, dict)
        and info.get("mapped_to") != "unknown"
        and info.get("mapped_to") in df.columns
    ]

    for original_col, col in confirmed_columns:
        if col == "_is_duplicate":
            continue
        rate = fill_rates.get(original_col, 1.0)  # Default to 1.0 (fully filled) if rate unknown
        if rate < 0.5:
            # Sparse column — flag once with fill rate context instead of flooding the report
            fill_pct = round(rate * 100)
            missing_pct = 100 - fill_pct
            issues.append({
                "row": "N/A",
                "column": col,
                "row_index": "N/A",
                "original_value": "N/A",
                "issue": (
                    f"Column '{col}' is {missing_pct}% empty (only {fill_pct}% filled). "
                    f"Confirm whether this is expected, if the data is missing, obtain the complete records before finalising your work"
                ),
                "severity": "medium"
            })
        else:
            # Normal column — flag each missing value individually so the auditor can address them
            for idx, value in df[col].items():
                if pd.isna(value) or str(value).strip() == "" or value == "":
                    issues.append({
                        "row": int(idx) + 2,
                        "column": col,
                        "row_index": idx,
                        "original_value": "",
                        "issue": f"Missing value in '{col}' — this field should not be empty. Check the source data and fill in the correct value.",
                        "severity": "medium"
                    })

    return df
    
# Function to detect and flag duplicate rows
def handle_duplicates(df: pd.DataFrame, mapping: dict, issues: list) -> pd.DataFrame:
    """
    Detect two issues:
    1. Exact duplicates, all column values identical. Flags and marks for removal.
    2. Suspicious duplicates, same date + amount + vendor but different ID. Flagged for auditor review.
    Does not remove any rows, auditor decides.
    """
    # Initialize marker column to avoid KeyError in suspicious check if no exact duplicates exist
    df["_is_duplicate"] = df.duplicated(keep="first")

    # Find all rows that are completely identical to another row
    exact_duplicates = df[df.duplicated(keep=False)]
    for idx in exact_duplicates.index:
        issues.append({
            "row": int(idx) + 2,
            "column": "all columns",
            "row_index": idx,
            "original_value": str(df.loc[idx].to_dict()),
            "issue": "This row is an exact duplicate of another row — check whether it was entered twice and remove the extra copy.",
            "severity": "high"
        })

    # Find all date and numeric columns using the mapping for suspicious duplicate check
    # Skip "unknown" mapped_to since those columns were left under their original name
    date_cols = [
        info["mapped_to"] for info in mapping.values()
        if isinstance(info, dict) and info.get("field_type") == "date"
        and info.get("mapped_to") != "unknown"
        and info.get("mapped_to") in df.columns
    ]
    amount_cols = [
        info["mapped_to"] for info in mapping.values()
        if isinstance(info, dict) and info.get("field_type") == "numeric"
        and info.get("mapped_to") != "unknown"
        and info.get("mapped_to") in df.columns
    ]
    # Combine date and numeric columns for suspicious duplicate check
    check_cols = date_cols + amount_cols
    # Only check if we have at least one date and one numeric column
    if date_cols and amount_cols:
        suspicious = df[
            df.duplicated(subset=check_cols, keep=False)
            # Exclude already flagged exact duplicates
            & ~df["_is_duplicate"]
        ]
        # Flag suspicious duplicates for auditor review
        for idx in suspicious.index:
            issues.append({
                "row": int(idx) + 2,
                "column": str(check_cols),
                "row_index": idx,
                "original_value": str(df.loc[idx][check_cols].to_dict()),
                "issue": "Same date and amount as another row, this may be a duplicate payment or entry. Verify before you proceed to analysis.",
                "severity": "medium"
            })
    return df

# Function to build the final validation report
def build_validation_report(df: pd.DataFrame, original_df: pd.DataFrame, issues: list) -> dict:
    """
    Build a summary validation report from all issues found during cleaning.
    Shows total rows, clean rows, flagged rows and a breakdown of issues by type and severity.
    """
    total_rows = len(original_df)
    flagged_rows = len(set(
        issue["row_index"]
        for issue in issues
        if "row_index" in issue and issue.get("severity") != "info" and issue["row_index"] != "N/A"
    ))
    clean_rows = total_rows - flagged_rows

    # Count issues by severity
    high_issues = [i for i in issues if i.get("severity") == "high"]
    medium_issues = [i for i in issues if i.get("severity") == "medium"]
    info_issues = [i for i in issues if i.get("severity") == "info"]
    # Build report dictionary
    return {
        "total_rows": total_rows,
        "clean_rows": clean_rows,
        "flagged_rows": flagged_rows,
        "total_issues": len(issues),
        "high_issues": len(high_issues),
        "medium_issues": len(medium_issues),
        "info_issues": len(info_issues),
        "issues": issues
    }


    