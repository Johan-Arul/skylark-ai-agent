# Decision Log

## Monday.com Business Intelligence Agent

Skylark Drones – Technical Assignment

---

# 1. Overview

This document outlines key assumptions, design choices, trade-offs, and interpretations made during development within the 6-hour constraint.

The focus was reliability, clarity, and founder-level usefulness.

---

# 2. Key Assumptions

## Board Structure

Deals Board:

- Deal Name
- Sector
- Deal Value
- Status
- Expected Close Date
- Probability (optional)

Work Orders Board:

- Project Name
- Linked Deal (optional)
- Revenue
- Status
- Start Date

---

## Data Linking

Assumed at least one of:

- Linked item column  
  OR
- Shared Deal ID / Name

Fallback: normalized name matching.

---

## Founder Query Style

Founders ask outcome-driven questions, not technical ones.

Responses must:

- Be concise
- Highlight insights
- Surface risks
- Include caveats

---

# 3. Architecture Decisions

---

## API Over MCP

Reason:

- Faster implementation
- Direct query control
- Simpler debugging

Trade-off:

- Manual schema handling

---

## Real-Time Queries

Reason:

- Avoid hardcoding
- Ensure live data accuracy

Trade-off:

- API latency
- No caching layer

---

## Python + Pandas

Reason:

- Strong data cleaning capabilities
- Fast aggregation
- Reliable date parsing

Trade-off:

- Not optimized for very large datasets

---

## No Database Layer

Reason:

- Simpler architecture
- Faster development
- Stateless design

Trade-off:

- Metrics recomputed each query

---

# 4. Data Resilience Strategy

## Numeric Normalization

- "10k" → 10000
- "₹10000" → 10000
- Null → 0 (flagged)

## Date Normalization

- Parse multiple formats
- Convert to ISO
- Exclude invalid dates
- Report missing values

## Text Standardization

- Lowercase
- Trim whitespace
- Map similar statuses

## Data Caveats

The agent explicitly reports:

- % missing sector
- % missing revenue
- % missing dates

Improves leadership trust.

---

# 5. Query Understanding Approach

Mapped natural language to intent categories:

| Query           | Interpretation     |
| --------------- | ------------------ |
| Pipeline        | Open deal value    |
| This quarter    | Date filter        |
| Overloaded      | Active work orders |
| Conversion rate | Closed / Total     |

Ambiguity → clarification question.

---

# 6. Leadership Update Interpretation

Interpreted as:

Generate concise executive-ready summary including:

- Pipeline value
- Sector breakdown
- Closed revenue
- Conversion rate
- Active projects
- Operational risk
- Data caveats

Goal: Decision-support, not raw data dump.

---

# 7. Trade-Offs Due to Time Constraint

Not implemented:

- Forecasting models
- Visual dashboards
- Advanced anomaly detection
- Resource-level operational modeling

Focus prioritized:

- Correctness
- Resilience
- Insight clarity

---

# 8. Risks & Mitigation

## Schema Changes

Mitigation: Dynamic column detection.

## Weak Board Linking

Mitigation: Fallback name matching.

## API Rate Limits

Mitigation: Pagination & minimal field queries.

---

# 9. Future Improvements

With more time:

1. Add caching layer
2. Add visualization dashboards
3. Add predictive revenue forecasting
4. Add anomaly detection
5. Automated weekly leadership summary
6. Data quality dashboard

---

# 10. Why This Design Works

The system:

- Handles messy real-world data
- Provides contextual insights
- Dynamically integrates with Monday.com
- Surfaces data quality limitations
- Supports leadership-level decision-making

It avoids over-engineering and focuses on reliability within a 6-hour build window.
