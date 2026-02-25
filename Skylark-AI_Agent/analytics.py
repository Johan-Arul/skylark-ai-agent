"""
analytics.py
Business Intelligence computation engine for Skylark Drones.
All metrics are computed in-memory from cleaned Pandas DataFrames.
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Optional


def _fmt_inr(value: float) -> str:
    """Format a float as Indian Rupee string (e.g., ₹12,34,56,789)."""
    if value == 0:
        return "₹0"
    if value >= 1e7:
        return f"₹{value/1e7:.2f} Cr"
    if value >= 1e5:
        return f"₹{value/1e5:.2f} L"
    if value >= 1e3:
        return f"₹{value/1e3:.1f}K"
    return f"₹{value:,.0f}"


def _current_quarter_bounds() -> tuple:
    """Return (start_date, end_date) for the current financial quarter."""
    today = date.today()
    month = today.month
    year = today.year

    # Financial year quarters: Apr-Jun, Jul-Sep, Oct-Dec, Jan-Mar
    if month in (4, 5, 6):
        q_start = date(year, 4, 1)
        q_end = date(year, 6, 30)
    elif month in (7, 8, 9):
        q_start = date(year, 7, 1)
        q_end = date(year, 9, 30)
    elif month in (10, 11, 12):
        q_start = date(year, 10, 1)
        q_end = date(year, 12, 31)
    else:  # Jan-Mar
        q_start = date(year, 1, 1)
        q_end = date(year, 3, 31)

    return pd.Timestamp(q_start), pd.Timestamp(q_end)


def _filter_by_period(df: pd.DataFrame, date_col: str, period: Optional[str]) -> pd.DataFrame:
    """Filter DataFrame rows by period string: 'this_quarter', 'this_month', 'ytd', or None (all)."""
    if period is None or df.empty or date_col not in df.columns:
        return df

    today = pd.Timestamp.today()

    if period == "this_month":
        mask = (df[date_col].dt.year == today.year) & (df[date_col].dt.month == today.month)
    elif period == "this_quarter":
        q_start, q_end = _current_quarter_bounds()
        mask = (df[date_col] >= q_start) & (df[date_col] <= q_end)
    elif period == "ytd":
        fy_start = pd.Timestamp(date(today.year if today.month >= 4 else today.year - 1, 4, 1))
        mask = df[date_col] >= fy_start
    else:
        return df

    return df[mask]


# ──────────────────────────────────────────────
# Revenue Analytics
# ──────────────────────────────────────────────

def revenue_analytics(deals_df: pd.DataFrame, period: Optional[str] = None) -> dict:
    """
    Compute closed revenue metrics from Won deals.
    Returns: closed_total, by_sector, by_month breakdown, and summary text.
    """
    if deals_df.empty:
        return {"error": "No deals data available."}

    won = deals_df[deals_df["status"] == "Won"].copy()

    if period:
        won = _filter_by_period(won, "close_date", period)

    if won.empty:
        return {
            "closed_total": 0,
            "closed_total_fmt": "₹0",
            "by_sector": {},
            "by_month": {},
            "count": 0,
            "summary": "No Won deals found for the selected period.",
        }

    closed_total = won["deal_value"].sum()

    # By sector
    by_sector = (
        won.groupby("sector")["deal_value"]
        .sum()
        .sort_values(ascending=False)
        .to_dict()
    )
    by_sector_fmt = {k: _fmt_inr(v) for k, v in by_sector.items()}

    # By month
    won_with_date = won.dropna(subset=["close_date"])
    if not won_with_date.empty:
        won_with_date = won_with_date.copy()
        won_with_date["month"] = won_with_date["close_date"].dt.to_period("M").astype(str)
        by_month = won_with_date.groupby("month")["deal_value"].sum().sort_index().to_dict()
        by_month_fmt = {k: _fmt_inr(v) for k, v in by_month.items()}
    else:
        by_month_fmt = {}

    # Top sector
    top_sector = max(by_sector, key=by_sector.get) if by_sector else "N/A"
    top_sector_pct = (by_sector.get(top_sector, 0) / closed_total * 100) if closed_total > 0 else 0

    return {
        "closed_total": closed_total,
        "closed_total_fmt": _fmt_inr(closed_total),
        "count": len(won),
        "by_sector": by_sector_fmt,
        "by_month": by_month_fmt,
        "top_sector": top_sector,
        "top_sector_pct": round(top_sector_pct, 1),
        "period": period or "all time",
    }


# ──────────────────────────────────────────────
# Pipeline Health
# ──────────────────────────────────────────────

def pipeline_health(deals_df: pd.DataFrame, period: Optional[str] = None) -> dict:
    """
    Compute open pipeline metrics.
    Returns: total pipeline, weighted pipeline, by sector, closing this quarter.
    """
    if deals_df.empty:
        return {"error": "No deals data available."}

    open_deals = deals_df[deals_df["status"] == "Open"].copy()

    if period:
        open_deals = _filter_by_period(open_deals, "close_date", period)

    if open_deals.empty:
        return {
            "pipeline_total": 0,
            "pipeline_total_fmt": "₹0",
            "weighted_pipeline": 0,
            "weighted_pipeline_fmt": "₹0",
            "count": 0,
            "by_sector": {},
            "closing_this_quarter": 0,
            "summary": "No open deals found.",
        }

    pipeline_total = open_deals["deal_value"].sum()
    weighted_pipeline = open_deals["weighted_value"].sum()

    # By sector
    by_sector = (
        open_deals.groupby("sector")["deal_value"]
        .sum()
        .sort_values(ascending=False)
        .to_dict()
    )
    by_sector_fmt = {k: _fmt_inr(v) for k, v in by_sector.items()}

    # Closing this quarter
    q_start, q_end = _current_quarter_bounds()
    closing_q = open_deals.dropna(subset=["close_date"])
    closing_q = closing_q[(closing_q["close_date"] >= q_start) & (closing_q["close_date"] <= q_end)]
    closing_value = closing_q["deal_value"].sum()

    # By probability band
    high_prob = open_deals[open_deals["probability"] >= 0.75]["deal_value"].sum()
    mid_prob = open_deals[(open_deals["probability"] >= 0.4) & (open_deals["probability"] < 0.75)]["deal_value"].sum()
    low_prob = open_deals[open_deals["probability"] < 0.4]["deal_value"].sum()

    return {
        "pipeline_total": pipeline_total,
        "pipeline_total_fmt": _fmt_inr(pipeline_total),
        "weighted_pipeline": weighted_pipeline,
        "weighted_pipeline_fmt": _fmt_inr(weighted_pipeline),
        "count": len(open_deals),
        "by_sector": by_sector_fmt,
        "closing_this_quarter_value": _fmt_inr(closing_value),
        "closing_this_quarter_count": len(closing_q),
        "high_prob_pipeline": _fmt_inr(high_prob),
        "mid_prob_pipeline": _fmt_inr(mid_prob),
        "low_prob_pipeline": _fmt_inr(low_prob),
        "period": period or "all time",
    }


# ──────────────────────────────────────────────
# Operational Metrics
# ──────────────────────────────────────────────

def operational_metrics(workorders_df: pd.DataFrame) -> dict:
    """
    Compute work order operational metrics.
    Returns: active WO count, by status, backlog value, revenue per project.
    """
    if workorders_df.empty:
        return {"error": "No work orders data available."}

    total = len(workorders_df)
    active = workorders_df[workorders_df["is_active"]]
    completed = workorders_df[workorders_df["exec_status"] == "Completed"]

    # By execution status
    by_status = workorders_df["exec_status"].value_counts().to_dict()

    # By sector
    by_sector = (
        active.groupby("sector")["amount_excl_gst"]
        .sum()
        .sort_values(ascending=False)
        .to_dict()
    )
    by_sector_fmt = {k: _fmt_inr(v) for k, v in by_sector.items()}

    # Backlog = sum of unbilled amounts on active WOs
    backlog = active["unbilled_amount"].sum()

    # Completed revenue
    completed_revenue = completed["amount_excl_gst"].sum()

    # Operational risk assessment
    if len(active) > 30:
        risk = "High"
        risk_note = f"{len(active)} active work orders — team may be stretched."
    elif len(active) > 15:
        risk = "Medium"
        risk_note = f"{len(active)} active work orders — manageable load."
    else:
        risk = "Low"
        risk_note = f"{len(active)} active work orders — comfortable capacity."

    paused = workorders_df[workorders_df["exec_status"] == "Paused"]

    return {
        "total_work_orders": total,
        "active_count": len(active),
        "completed_count": len(completed),
        "paused_count": len(paused),
        "by_status": by_status,
        "active_by_sector": by_sector_fmt,
        "backlog_value": _fmt_inr(backlog),
        "backlog_raw": backlog,
        "completed_revenue": _fmt_inr(completed_revenue),
        "operational_risk": risk,
        "risk_note": risk_note,
    }


# ──────────────────────────────────────────────
# Cross-Board Analysis
# ──────────────────────────────────────────────

def cross_board_analysis(deals_df: pd.DataFrame, workorders_df: pd.DataFrame) -> dict:
    """
    Link Deals and Work Orders boards and compute conversion metrics.
    Uses deal_name matching (normalized) as the linkage key.
    """
    if deals_df.empty or workorders_df.empty:
        return {"error": "Both deals and work orders data are required for cross-board analysis."}

    # Normalize names for matching
    deals_df = deals_df.copy()
    workorders_df = workorders_df.copy()
    deals_df["_name_norm"] = deals_df["deal_name"].str.strip().str.lower()
    workorders_df["_name_norm"] = workorders_df["deal_name_linked"].str.strip().str.lower()

    # Conversion rate: Won deals → have a matching Work Order
    won = deals_df[deals_df["status"] == "Won"]
    won_names = set(won["_name_norm"].unique())
    wo_names = set(workorders_df["_name_norm"].unique())
    matched = won_names & wo_names
    conversion_count = len(matched)
    total_open_closed = len(deals_df[deals_df["status"].isin(["Open", "Won"])])
    won_count = len(won)

    conversion_rate = round(100 * won_count / total_open_closed, 1) if total_open_closed > 0 else 0
    wo_coverage_rate = round(100 * conversion_count / won_count, 1) if won_count > 0 else 0

    # Pipeline vs realized revenue
    total_pipeline = deals_df[deals_df["status"] == "Open"]["deal_value"].sum()
    total_closed = won["deal_value"].sum()
    total_wo_value = workorders_df["amount_excl_gst"].sum()

    # Sector performance cross-board
    won_by_sector = won.groupby("sector")["deal_value"].sum().rename("won_value")
    wo_by_sector = workorders_df.groupby("sector")["amount_excl_gst"].sum().rename("wo_value")
    sector_perf = pd.concat([won_by_sector, wo_by_sector], axis=1).fillna(0)
    sector_perf["realization_rate"] = (
        sector_perf["wo_value"] / sector_perf["won_value"] * 100
    ).where(sector_perf["won_value"] > 0, 0).round(1)
    sector_perf_dict = sector_perf.to_dict(orient="index")
    sector_perf_fmt = {
        k: {
            "won_pipeline": _fmt_inr(v["won_value"]),
            "wo_value": _fmt_inr(v["wo_value"]),
            "realization_rate_pct": v["realization_rate"],
        }
        for k, v in sector_perf_dict.items()
    }

    return {
        "won_deals_count": won_count,
        "conversion_rate_pct": conversion_rate,
        "wo_coverage_rate_pct": wo_coverage_rate,
        "total_pipeline": _fmt_inr(total_pipeline),
        "closed_revenue": _fmt_inr(total_closed),
        "total_wo_value": _fmt_inr(total_wo_value),
        "sector_performance": sector_perf_fmt,
    }


# ──────────────────────────────────────────────
# Leadership Update
# ──────────────────────────────────────────────

def generate_leadership_update(
    deals_df: pd.DataFrame,
    workorders_df: pd.DataFrame,
    caveats: dict,
) -> dict:
    """
    Generate a structured executive-ready summary for founders.
    Combines pipeline health, revenue, operations, and cross-board metrics.
    """
    q_start, q_end = _current_quarter_bounds()
    q_label = f"Q{pd.Timestamp.today().quarter} FY{pd.Timestamp.today().year}"

    rev = revenue_analytics(deals_df, period="ytd")
    pipeline = pipeline_health(deals_df, period="this_quarter")
    ops = operational_metrics(workorders_df)
    cross = cross_board_analysis(deals_df, workorders_df)

    update = {
        "title": f"Leadership Update — {q_label}",
        "generated_at": datetime.now().strftime("%d %b %Y, %H:%M IST"),
        "pipeline": {
            "total_open_pipeline": pipeline.get("pipeline_total_fmt", "N/A"),
            "weighted_pipeline": pipeline.get("weighted_pipeline_fmt", "N/A"),
            "closing_this_quarter": pipeline.get("closing_this_quarter_value", "N/A"),
            "by_sector": pipeline.get("by_sector", {}),
        },
        "revenue": {
            "closed_ytd": rev.get("closed_total_fmt", "N/A"),
            "top_sector": rev.get("top_sector", "N/A"),
            "top_sector_share_pct": rev.get("top_sector_pct", 0),
            "by_sector": rev.get("by_sector", {}),
        },
        "operations": {
            "active_work_orders": ops.get("active_count", 0),
            "completed_work_orders": ops.get("completed_count", 0),
            "backlog_value": ops.get("backlog_value", "N/A"),
            "operational_risk": ops.get("operational_risk", "N/A"),
            "risk_note": ops.get("risk_note", ""),
        },
        "conversion": {
            "won_to_total_rate_pct": cross.get("conversion_rate_pct", 0),
            "wo_coverage_rate_pct": cross.get("wo_coverage_rate_pct", 0),
        },
        "data_quality": caveats,
    }

    return update


def format_leadership_update(update: dict) -> str:
    """Format a leadership update dict into a clean markdown string."""
    lines = [
        f"## 📊 {update['title']}",
        f"*Generated: {update['generated_at']}*",
        "",
        "### 💰 Pipeline",
        f"- **Total Open Pipeline:** {update['pipeline']['total_open_pipeline']}",
        f"- **Weighted Pipeline:** {update['pipeline']['weighted_pipeline']}",
        f"- **Closing This Quarter:** {update['pipeline']['closing_this_quarter']}",
    ]

    if update['pipeline']['by_sector']:
        lines.append("- **By Sector:**")
        for sector, val in list(update['pipeline']['by_sector'].items())[:5]:
            lines.append(f"  - {sector.title()}: {val}")

    lines += [
        "",
        "### 📈 Revenue (YTD)",
        f"- **Closed Revenue:** {update['revenue']['closed_ytd']}",
        f"- **Top Sector:** {update['revenue']['top_sector'].title()} ({update['revenue']['top_sector_share_pct']}% of closed revenue)",
    ]

    lines += [
        "",
        "### 🔧 Operations",
        f"- **Active Work Orders:** {update['operations']['active_work_orders']}",
        f"- **Completed Work Orders:** {update['operations']['completed_work_orders']}",
        f"- **Unbilled Backlog:** {update['operations']['backlog_value']}",
        f"- **Operational Risk:** {update['operations']['operational_risk']} — {update['operations']['risk_note']}",
    ]

    lines += [
        "",
        "### 🔄 Conversion",
        f"- **Deal Win Rate:** {update['conversion']['won_to_total_rate_pct']}%",
        f"- **Won → Work Order Coverage:** {update['conversion']['wo_coverage_rate_pct']}%",
    ]

    dq = update.get("data_quality", {})
    if dq:
        notes = []
        if dq.get("deals_missing_revenue_pct", 0) > 10:
            notes.append(f"{dq['deals_missing_revenue_pct']}% of deals have no value (revenue may be understated)")
        if dq.get("deals_missing_sector_pct", 0) > 10:
            notes.append(f"{dq['deals_missing_sector_pct']}% of deals have no sector (sector breakdown is partial)")
        if dq.get("wo_missing_amount_pct", 0) > 10:
            notes.append(f"{dq['wo_missing_amount_pct']}% of work orders have no amount")
        if notes:
            lines += ["", "### ⚠️ Data Caveats"]
            for note in notes:
                lines.append(f"- {note}")

    return "\n".join(lines)
