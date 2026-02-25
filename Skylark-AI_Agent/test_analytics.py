"""
test_analytics.py — Integration test using real Skylark Drones CSV data.
"""
import pandas as pd
from data_cleaner import (
    clean_deals_df, clean_workorders_df, compute_caveats, format_caveats_text
)
from analytics import (
    revenue_analytics, pipeline_health, operational_metrics,
    cross_board_analysis
)


def df_to_items(df):
    items = []
    for i, row in df.iterrows():
        item = {"_item_id": str(i), "_item_name": str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""}
        for col in df.columns:
            item[col] = str(row[col]) if pd.notna(row[col]) else ""
        items.append(item)
    return items


def make_schema(df, board_name):
    cols = {col.strip(): {"title": col.strip(), "type": "text"} for col in df.columns}
    return {"board_name": board_name, "columns": cols}


# Load CSV files
deals_raw_df = pd.read_csv("Deal_funnel_Data.csv", on_bad_lines="skip")
wo_raw_df = pd.read_csv("Work_Order_Tracker_Data.csv", on_bad_lines="skip", header=1)

deals_items = df_to_items(deals_raw_df)
wo_items = df_to_items(wo_raw_df)
deals_schema = make_schema(deals_raw_df, "Deals")
wo_schema = make_schema(wo_raw_df, "Work Orders")

deals_df = clean_deals_df(deals_items, deals_schema)
wo_df = clean_workorders_df(wo_items, wo_schema)

print(f"Deals loaded: {len(deals_df)} rows")
open_cnt = len(deals_df[deals_df["status"] == "Open"])
won_cnt = len(deals_df[deals_df["status"] == "Won"])
dead_cnt = len(deals_df[deals_df["status"] == "Dead"])
print(f"  - Open: {open_cnt} | Won: {won_cnt} | Dead: {dead_cnt}")
print(f"Work Orders loaded: {len(wo_df)} rows")
print(f"  - Active: {wo_df['is_active'].sum()} | Completed: {(wo_df['exec_status'] == 'Completed').sum()}")
print()

rev = revenue_analytics(deals_df)
pipe = pipeline_health(deals_df)
ops = operational_metrics(wo_df)
cross = cross_board_analysis(deals_df, wo_df)

print("== REVENUE ==")
print(f"  Closed (all time): {rev['closed_total_fmt']}")
print(f"  Won deals: {rev['count']}")
print(f"  Top sector: {rev['top_sector']} ({rev['top_sector_pct']}%)")
print(f"  By sector: {rev['by_sector']}")
print()

print("== PIPELINE ==")
print(f"  Open pipeline: {pipe['pipeline_total_fmt']}")
print(f"  Weighted: {pipe['weighted_pipeline_fmt']}")
print(f"  High prob: {pipe['high_prob_pipeline']}")
print(f"  Closing this Q: {pipe['closing_this_quarter_value']} ({pipe['closing_this_quarter_count']} deals)")
print()

print("== OPERATIONS ==")
print(f"  Active WOs: {ops['active_count']}")
print(f"  Completed: {ops['completed_count']}")
print(f"  Paused: {ops['paused_count']}")
print(f"  Backlog: {ops['backlog_value']}")
print(f"  Risk: {ops['operational_risk']} — {ops['risk_note']}")
print()

print("== CROSS-BOARD ==")
print(f"  Win rate: {cross['conversion_rate_pct']}%")
print(f"  WO coverage: {cross['wo_coverage_rate_pct']}%")
print(f"  Total pipeline: {cross['total_pipeline']}")
print(f"  Closed revenue: {cross['closed_revenue']}")
print(f"  Total WO value: {cross['total_wo_value']}")
print()

caveats = compute_caveats(deals_df, wo_df)
caveat_text = format_caveats_text(caveats)
print("== CAVEATS ==")
print(caveat_text if caveat_text else "No significant data quality issues.")
print()
print("ALL ANALYTICS OK")
