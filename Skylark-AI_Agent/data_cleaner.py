"""
data_cleaner.py
Data normalization and cleaning layer for Skylark Drones BI Agent.
Handles messy real-world data from Monday.com boards.
"""

import re
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional


# ──────────────────────────────────────────────
# Primitive normalizers
# ──────────────────────────────────────────────

def normalize_revenue(value) -> float:
    """
    Converts messy revenue strings to float.
    Handles: "10k", "₹10,000", "1.2L", JSON strings, None, ""
    Returns 0.0 on failure.
    """
    if value is None or value == "" or (isinstance(value, float) and np.isnan(value)):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    # Try to extract from JSON value strings (Monday.com sometimes returns JSON)
    if text.startswith("{") or text.startswith('"'):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                text = str(parsed.get("value", parsed.get("text", "")))
            elif isinstance(parsed, (int, float)):
                return float(parsed)
        except Exception:
            pass

    # Remove currency symbols, text prefixes, commas, spaces
    text = re.sub(r"(?i)(rs\.?|inr|usd|eur|£|€|\$|₹)", "", text)
    text = re.sub(r"[,\s]", "", text)

    # Handle shorthand: 10k, 1.5L, 2.5Cr
    multiplier = 1.0
    if text.lower().endswith("cr"):
        multiplier = 1e7
        text = text[:-2]
    elif text.lower().endswith("l"):
        multiplier = 1e5
        text = text[:-1]
    elif text.lower().endswith("k"):
        multiplier = 1e3
        text = text[:-1]

    try:
        return float(text) * multiplier
    except (ValueError, TypeError):
        return 0.0


def normalize_date(value) -> Optional[str]:
    """
    Parses various date formats and returns ISO date string (YYYY-MM-DD) or None.
    Handles: "2025-12-31", "31/12/2025", "Dec 31, 2025", Monday.com JSON, etc.
    """
    if not value or value == "" or (isinstance(value, float) and np.isnan(value)):
        return None

    text = str(value).strip()

    # Monday.com date column returns JSON like {"date":"2025-12-31"}
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            text = parsed.get("date", "")
            if not text:
                return None
        except Exception:
            pass

    FORMATS = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%m-%Y", "%d %b %Y", "%B %d, %Y",
        "%d %B %Y", "%Y/%m/%d",
    ]
    for fmt in FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_text(value) -> str:
    """Lowercase + strip whitespace for consistent text comparison."""
    if not value:
        return ""
    return str(value).strip().lower()


# ──────────────────────────────────────────────
# Deal Stage → Category mapping
# ──────────────────────────────────────────────

DEAD_STAGES = {"n. not relevant at the moment", "o. not relevant at all", "l. project lost", "m. projects on hold"}
WON_STAGES = {"h. work order received", "project completed", "k. amount accrued", "g. project won", "j. invoice sent", "i. poc"}
OPEN_STAGES = {
    "a. lead generated", "b. sales qualified leads", "c. demo done",
    "d. feasibility", "e. proposal/commercials sent", "f. negotiations",
}

PROBABILITY_MAP = {"high": 0.80, "medium": 0.50, "low": 0.25, "": 0.0}


def map_deal_status(status: str, stage: str) -> str:
    """Determine canonical deal status from status + stage fields."""
    s = normalize_text(status)
    st = normalize_text(stage)

    if s == "won":
        return "Won"
    if s == "dead":
        return "Dead"
    if s == "on hold":
        return "On Hold"
    if st in WON_STAGES:
        return "Won"
    if st in DEAD_STAGES:
        return "Dead"
    if st in OPEN_STAGES:
        return "Open"
    return "Open"  # default


# ──────────────────────────────────────────────
# Schema-aware column resolution
# ──────────────────────────────────────────────

def find_column(item: dict, schema_columns: dict, keywords: list) -> str:
    """
    Find the best matching column value from an item using keyword hints.
    Searches column titles (case-insensitive) for any of the given keywords.
    Returns empty string if not found.
    """
    kw_lower = [k.lower() for k in keywords]
    for col_id, col_meta in schema_columns.items():
        title = col_meta["title"].lower()
        if any(kw in title for kw in kw_lower):
            return item.get(col_id, "")
    return ""


# ──────────────────────────────────────────────
# Board-specific cleaning pipelines
# ──────────────────────────────────────────────

def clean_deals_df(raw_items: list, schema: dict) -> pd.DataFrame:
    """
    Clean and normalize raw Deals board items into a structured DataFrame.
    Uses schema for dynamic column detection.
    """
    if not raw_items:
        return pd.DataFrame()

    cols = schema.get("columns", {})
    records = []

    for item in raw_items:
        name = str(item.get("_item_name", "")).strip()
        if not name or name.lower() in ("deal name", ""):
            continue  # skip header-like rows

        status_raw = find_column(item, cols, ["status", "deal status"])
        stage_raw = find_column(item, cols, ["stage", "deal stage"])
        sector_raw = find_column(item, cols, ["sector", "service"])
        value_raw = find_column(item, cols, ["value", "deal value", "masked"])
        close_date_raw = find_column(item, cols, ["close date", "actual close", "close date (a)"])
        tentative_date_raw = find_column(item, cols, ["tentative", "expected close"])
        probability_raw = find_column(item, cols, ["probability", "closure"])
        owner_raw = find_column(item, cols, ["owner", "personnel"])
        client_raw = find_column(item, cols, ["client", "company"])
        product_raw = find_column(item, cols, ["product"])
        created_raw = find_column(item, cols, ["created", "creation"])

        canonical_status = map_deal_status(status_raw, stage_raw)
        revenue = normalize_revenue(value_raw)
        probability = PROBABILITY_MAP.get(normalize_text(probability_raw), 0.0)
        sector = normalize_text(sector_raw) or "unknown"
        close_date = normalize_date(close_date_raw) or normalize_date(tentative_date_raw)
        created_date = normalize_date(created_raw)

        records.append({
            "deal_name": name,
            "owner_code": str(owner_raw).strip(),
            "client_code": str(client_raw).strip(),
            "status": canonical_status,
            "stage": normalize_text(stage_raw),
            "sector": sector,
            "deal_value": revenue,
            "probability": probability,
            "weighted_value": revenue * probability,
            "close_date": close_date,
            "created_date": created_date,
            "product": str(product_raw).strip(),
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Parse date columns as datetime
    for dc in ["close_date", "created_date"]:
        df[dc] = pd.to_datetime(df[dc], errors="coerce")

    return df


def clean_workorders_df(raw_items: list, schema: dict) -> pd.DataFrame:
    """
    Clean and normalize raw Work Orders board items into a structured DataFrame.
    """
    if not raw_items:
        return pd.DataFrame()

    cols = schema.get("columns", {})
    records = []

    for item in raw_items:
        name = str(item.get("_item_name", "")).strip()
        if not name:
            continue

        deal_name_raw = find_column(item, cols, ["deal name", "deal"])
        exec_status_raw = find_column(item, cols, ["execution status", "exec status", "status"])
        sector_raw = find_column(item, cols, ["sector"])
        amount_excl_raw = find_column(item, cols, ["amount in rupees (excl", "excl of gst", "excl. of gst"])
        amount_incl_raw = find_column(item, cols, ["amount in rupees (incl", "incl of gst"])
        billed_excl_raw = find_column(item, cols, ["billed value in rupees (excl", "billed value"])
        wo_status_raw = find_column(item, cols, ["wo status", "billing status", "collection status"])
        start_date_raw = find_column(item, cols, ["probable start", "start date", "date of po"])
        end_date_raw = find_column(item, cols, ["probable end", "end date", "delivery date"])
        nature_raw = find_column(item, cols, ["nature of work", "nature"])
        owner_raw = find_column(item, cols, ["bd/kam", "owner", "personnel"])
        invoice_raw = find_column(item, cols, ["invoice", "billed"])

        amount = normalize_revenue(amount_excl_raw) or normalize_revenue(amount_incl_raw)
        billed = normalize_revenue(billed_excl_raw)
        exec_status = normalize_text(exec_status_raw)
        sector = normalize_text(sector_raw) or "unknown"

        # Normalize execution status to clean categories
        if "completed" in exec_status:
            exec_status_clean = "Completed"
        elif "ongoing" in exec_status or "executed until" in exec_status:
            exec_status_clean = "Ongoing"
        elif "not started" in exec_status:
            exec_status_clean = "Not Started"
        elif "pause" in exec_status or "struck" in exec_status:
            exec_status_clean = "Paused"
        elif "partial" in exec_status:
            exec_status_clean = "Partially Completed"
        elif "pending" in exec_status or "details pending" in exec_status:
            exec_status_clean = "Pending"
        else:
            exec_status_clean = "Unknown"

        is_active = exec_status_clean in ("Ongoing", "Not Started", "Paused", "Partially Completed", "Pending")

        records.append({
            "wo_name": name,
            "deal_name_linked": str(deal_name_raw).strip() if deal_name_raw else name,
            "sector": sector,
            "exec_status": exec_status_clean,
            "is_active": is_active,
            "amount_excl_gst": amount,
            "billed_excl_gst": billed,
            "unbilled_amount": max(0.0, amount - billed),
            "wo_status": normalize_text(wo_status_raw),
            "nature_of_work": str(nature_raw).strip(),
            "owner_code": str(owner_raw).strip(),
            "start_date": normalize_date(start_date_raw),
            "end_date": normalize_date(end_date_raw),
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    for dc in ["start_date", "end_date"]:
        df[dc] = pd.to_datetime(df[dc], errors="coerce")

    return df


# ──────────────────────────────────────────────
# Data quality caveats
# ──────────────────────────────────────────────

def compute_caveats(deals_df: pd.DataFrame, workorders_df: pd.DataFrame) -> dict:
    """
    Calculate data quality metrics for transparency in responses.
    Returns percentages of missing key fields.
    """
    caveats = {}

    if not deals_df.empty:
        n = len(deals_df)
        caveats["deals_missing_revenue_pct"] = round(100 * (deals_df["deal_value"] == 0).sum() / n, 1)
        caveats["deals_missing_sector_pct"] = round(100 * (deals_df["sector"] == "unknown").sum() / n, 1)
        caveats["deals_missing_close_date_pct"] = round(100 * deals_df["close_date"].isna().sum() / n, 1)
        caveats["deals_total"] = n

    if not workorders_df.empty:
        n = len(workorders_df)
        caveats["wo_missing_amount_pct"] = round(100 * (workorders_df["amount_excl_gst"] == 0).sum() / n, 1)
        caveats["wo_missing_sector_pct"] = round(100 * (workorders_df["sector"] == "unknown").sum() / n, 1)
        caveats["wo_total"] = n

    return caveats


def format_caveats_text(caveats: dict) -> str:
    """Format caveats dict into a readable warning string."""
    lines = []
    if caveats.get("deals_missing_revenue_pct", 0) > 10:
        lines.append(f"⚠️ {caveats['deals_missing_revenue_pct']}% of deals have no deal value — revenue figures may be understated.")
    if caveats.get("deals_missing_sector_pct", 0) > 10:
        lines.append(f"⚠️ {caveats['deals_missing_sector_pct']}% of deals have no sector — sector breakdowns are partial.")
    if caveats.get("deals_missing_close_date_pct", 0) > 20:
        lines.append(f"⚠️ {caveats['deals_missing_close_date_pct']}% of deals have no close date — time-based filters may miss some deals.")
    if caveats.get("wo_missing_amount_pct", 0) > 10:
        lines.append(f"⚠️ {caveats['wo_missing_amount_pct']}% of work orders have no amount — revenue from operations may be understated.")
    return "\n".join(lines) if lines else ""
