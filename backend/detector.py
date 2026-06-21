import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

FILE_TYPE_CATEGORIES = {
    "fixed_assets": "Fixed Assets Register",
    "bank_transactions": "Bank Transactions",
    "payroll": "Payroll",
    "general_ledger": "General Ledger",
    "accounts_receivable": "Accounts Receivable",
    "accounts_payable": "Accounts Payable",
    "inventory": "Inventory",
    "other": "Other",
}

# =========================
# COLUMN DETECTION (LLM)
# =========================
def detect_columns_with_llm(columns: list, sample_values: dict = None, fill_rates: dict = None) -> dict:

    sample_values = sample_values or {}
    fill_rates = fill_rates or {}

    lower_to_original = {}
    lowercase_columns = []

    for col in columns:
        key = col.lower().strip()
        lower_to_original[key] = col
        lowercase_columns.append(key)

    lowercase_samples = {
        k.lower().strip(): v for k, v in sample_values.items()
    }

    lowercase_fill_rates = {
        k.lower().strip(): v for k, v in fill_rates.items()
    }

    columns_context = json.dumps([
        {
            "column": col,
            "sample": str(lowercase_samples.get(col, "")),
            "fill_rate": lowercase_fill_rates.get(col, 1.0)
        }
        for col in lowercase_columns
    ])

    prompt = f"""
You are a financial data expert.

Map each column to:
- mapped_to (snake_case field name)
- field_type: numeric | date | text | unknown

Rules:
- If fill_rate < 0.20 → ALWAYS unknown
- Use sample value for context
- Be consistent and conservative
- Return valid JSON only

Columns:
{columns_context}

Return format:
{{
  "column": {{
    "mapped_to": "field_name",
    "field_type": "text"
  }}
}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Return ONLY JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        llm_result = json.loads(raw)
    except json.JSONDecodeError:
        llm_result = {}

    final_mapping = {}

    for lower_col, original_col in lower_to_original.items():

        result = llm_result.get(lower_col, {})

        mapped_to = result.get("mapped_to", "unknown")
        field_type = result.get("field_type", "unknown")

        # normalize
        if not isinstance(mapped_to, str):
            mapped_to = "unknown"
        if field_type not in ["numeric", "date", "text", "unknown"]:
            field_type = "unknown"

        fill_rate = lowercase_fill_rates.get(lower_col, 1.0)

        # =========================
        # FINAL RULE (IMPORTANT FIX)
        # =========================
        if fill_rate < 0.20:
            mapped_to = "unknown"
            field_type = "unknown"

        final_mapping[original_col] = {
            "mapped_to": mapped_to,
            "field_type": field_type
        }

    return final_mapping


# =========================
# FILE TYPE DETECTION
# =========================
def suggest_file_type(columns: list, sample_values: dict = None) -> dict:

    sample_values = sample_values or {}

    columns_context = json.dumps([
        {"column": c, "sample": str(sample_values.get(c, ""))}
        for c in columns
    ])

    allowed = list(FILE_TYPE_CATEGORIES.keys())

    prompt = f"""
Classify file into ONE category from:
{allowed}

Columns:
{columns_context}

Return ONLY:
{{"file_type": "accounts_payable"}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Return ONLY JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=100,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(raw)
        file_type = result.get("file_type", "other")
    except:
        file_type = "other"

    if file_type not in FILE_TYPE_CATEGORIES:
        file_type = "other"

    return {
        "file_type": file_type,
        "file_type_label": FILE_TYPE_CATEGORIES[file_type]
    }


# =========================
# RESULT BUILDER
# =========================
def build_detection_result(columns: list, final_mapping: dict, sample_values: dict = None, fill_rates: dict = None):

    sample_values = sample_values or {}
    fill_rates = fill_rates or {}

    enriched = {}

    for col, info in final_mapping.items():
        enriched[col] = {
            **info,
            "sample_value": sample_values.get(col, ""),
            "fill_rate": fill_rates.get(col, 1.0)
        }

    unknown_columns = [
        c for c, i in enriched.items()
        if i["mapped_to"] == "unknown"
    ]

    warnings = []
    if unknown_columns:
        warnings.append({
            "type": "unknown_columns",
            "message": f"{len(unknown_columns)} column(s) need review",
            "columns": unknown_columns,
            "action": "Manually map or skip"
        })

    return {
        "total_columns": len(columns),
        "mapping": enriched,
        "unknown_count": len(unknown_columns),
        "warnings": warnings,
        "requires_manual_mapping": len(unknown_columns) > 0
    }