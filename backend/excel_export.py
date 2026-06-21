from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# Styles
HEADER_FILL   = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
HEADER_FONT   = Font(color="FFFFFF", bold=True, name="Arial", size=10)
FILL_HIGH     = PatternFill(start_color="FFDAD9", end_color="FFDAD9", fill_type="solid")
FILL_MEDIUM   = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
FILL_INFO     = PatternFill(start_color="EAF0FB", end_color="EAF0FB", fill_type="solid")
FILL_CLEAN    = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
NORMAL_FONT   = Font(name="Arial", size=10)
BOLD_FONT     = Font(bold=True, name="Arial", size=10)
CENTER_ALIGN  = Alignment(vertical="center", horizontal="center")
LEFT_ALIGN    = Alignment(vertical="center", horizontal="left")
WRAP_ALIGN    = Alignment(wrap_text=True, vertical="top", horizontal="left")
SEV_FILLS  = {"high": FILL_HIGH, "medium": FILL_MEDIUM, "info": FILL_INFO}
SEV_LABELS = {"high": "HIGH", "medium": "MEDIUM", "info": "INFO"}
SEV_ORDER  = {"high": 0, "medium": 1, "info": 2}

# Helper to map row index to highest severity issue for that row, used for coloring rows in cleaned data sheet
def _row_severity_map(issues: list) -> dict:
    result = {}
    for issue in issues:
        ri = issue.get("row_index")
        if ri in (None, "N/A"):
            continue
        try:
            ri = int(ri)
        except (ValueError, TypeError):
            continue
        sev = issue.get("severity", "medium")
        if ri not in result or SEV_ORDER.get(sev, 1) < SEV_ORDER.get(result[ri], 1):
            result[ri] = sev
    return result

# Main function to build the Excel workbook with cleaned data and issues report, returns as BytesIO for sending as file response
def build_cleaning_workbook(cleaned_df, report: dict, mapping: dict) -> BytesIO:
    issues      = report.get("issues", [])
    row_sev_map = _row_severity_map(issues)
    # Exclude internal columns from display
    columns = [c for c in cleaned_df.columns if c not in ("_is_duplicate",)]
    wb = Workbook()

    # SHEET1 is Cleaned Data, Mirrors exactly what the frontend table shows, all rows, highlighted
    ws = wb.active
    ws.title = "Cleaned Data"
    # Header: # column then all data columns
    ws.cell(1, 1).value     = "#"
    ws.cell(1, 1).fill      = HEADER_FILL
    ws.cell(1, 1).font      = HEADER_FONT
    ws.cell(1, 1).alignment = CENTER_ALIGN
    # Data columns
    for col_idx, col_name in enumerate(columns, start=2):
        cell           = ws.cell(1, col_idx)
        cell.value     = col_name
        cell.fill      = HEADER_FILL
        cell.font      = HEADER_FONT
        cell.alignment = CENTER_ALIGN
    ws.row_dimensions[1].height = 20

    # Data rows
    for df_index, row in cleaned_df.iterrows():
        excel_row = int(df_index) + 2
        sev       = row_sev_map.get(int(df_index))
        row_fill  = SEV_FILLS.get(sev, FILL_CLEAN)

        # # column, same number shown on screen
        nr_cell           = ws.cell(excel_row, 1)
        # matches what is shown on the CleanPage table (row_index + 2, or N/A)
        nr_cell.value     = excel_row          
        nr_cell.fill      = row_fill
        nr_cell.font      = BOLD_FONT
        nr_cell.alignment = CENTER_ALIGN

        # data columns
        for col_idx, col_name in enumerate(columns, start=2):
            cell  = ws.cell(excel_row, col_idx)
            value = row[col_name]
            # Write blank for None/nan, never inject 0 for missing
            cell.value     = "" if value is None or str(value).strip().lower() in ("nan", "none", "") else value
            cell.fill      = row_fill
            cell.font      = NORMAL_FONT
            cell.alignment = LEFT_ALIGN

    # Column widths
    ws.column_dimensions["A"].width = 6
    for col_idx, col_name in enumerate(columns, start=2):
        try:
            max_len = max(
                len(str(col_name)),
                max((len(str(v)) for v in cleaned_df[col_name].head(200)
                     if v is not None and str(v).lower() not in ("nan", "none", "")), default=0)
            )
        except (ValueError, TypeError):
            max_len = len(str(col_name))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 40)
    ws.freeze_panes = "B2"

    # SHEET2 is Issues, Mirrors exactly what the Issues Found section shows on screen
    iss_ws = wb.create_sheet("Issues")
    iss_headers = ["Severity", "Row", "Column", "Original Value", "Issue"]
    for col_idx, h in enumerate(iss_headers, start=1):
        cell           = iss_ws.cell(1, col_idx)
        cell.value     = h
        cell.fill      = HEADER_FILL
        cell.font      = HEADER_FONT
        cell.alignment = CENTER_ALIGN
    iss_ws.row_dimensions[1].height = 20

    # Sort: high first, then medium, then info, then by row number
    def sort_key(iss):
        sev = SEV_ORDER.get(iss.get("severity", "info"), 2)
        try:    rn = int(iss.get("row_index", 99999))
        except: rn = 99999
        return (sev, rn)
    # Add issues to sheet, with same coloring and formatting as frontend table, including original value only when present, and wrap text for issue description
    for issue in sorted(issues, key=sort_key):
        sev      = issue.get("severity", "medium")
        ri       = issue.get("row_index", "N/A")
        col      = issue.get("column", "")
        orig_val = issue.get("original_value", "")
        desc     = issue.get("issue", "")

        # Display row matches what CleanPage shows: row_index + 2, or N/A for missing-value issues without row index
        try:    display_row = int(ri) + 2
        except: display_row = "N/A"

        # Only show original value when there is one, if no original value, hides the "Original value:" line entirely for missing-value issues
        orig_display = str(orig_val) if orig_val and str(orig_val).strip() not in ("", "N/A") else ""
        fill = SEV_FILLS.get(sev, FILL_MEDIUM)
        iss_ws.append([
            SEV_LABELS.get(sev, sev.upper()),
            display_row,
            col,
            orig_display,
            desc,
        ])
        r = iss_ws.max_row
        # Apply fill to entire row, bold font for severity and row/column, wrap text for issue description, adjust row height based on description length
        for c_idx in range(1, 6):
            cell           = iss_ws.cell(r, c_idx)
            cell.fill      = fill
            cell.font      = BOLD_FONT if c_idx in (1, 2) else NORMAL_FONT
            cell.alignment = WRAP_ALIGN if c_idx == 5 else LEFT_ALIGN
        iss_ws.row_dimensions[r].height = 40 if len(str(desc)) > 80 else 20
    for col_idx, width in {1: 12, 2: 8, 3: 26, 4: 22, 5: 70}.items():
        iss_ws.column_dimensions[get_column_letter(col_idx)].width = width
    iss_ws.freeze_panes    = "A2"
    iss_ws.auto_filter.ref = "A1:E1"
    # Save 
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer