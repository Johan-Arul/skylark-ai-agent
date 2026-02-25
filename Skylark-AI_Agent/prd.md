# Product Requirements Document (PRD)

## Monday.com Business Intelligence Agent

Skylark Drones

---

# 1. Executive Summary

This project delivers a conversational AI Business Intelligence (BI) agent that connects to Monday.com (read-only) and answers founder-level business questions using:

- Work Orders board (execution data)
- Deals board (sales pipeline data)

The system dynamically retrieves live data via Monday.com API, cleans messy data, performs cross-board analysis, and generates contextual business insights suitable for leadership decision-making.

No CSV hardcoding is allowed.

---

# 2. Problem Statement

Founders need quick answers such as:

- How is our pipeline looking this quarter?
- What revenue can we expect this month?
- Are we operationally overloaded?
- What is our deal-to-project conversion rate?

Currently this requires:

- Manual exports
- Spreadsheet cleanup
- Cross-board joins
- Custom analysis

This process is slow, error-prone, and not scalable.

---

# 3. Goals

## Primary Goal

Build a hosted conversational AI agent that:

1. Integrates with Monday.com (read-only)
2. Handles messy real-world data
3. Understands ambiguous business queries
4. Performs cross-board analytics
5. Provides contextual insights (not just numbers)

---

# 4. Scope

## In Scope

- Monday.com API integration
- Dynamic board schema detection
- Data cleaning & normalization
- Conversational query interface
- Cross-board analytics
- Leadership summary generation
- Graceful error handling

## Out of Scope

- Writing data back to Monday.com
- Predictive ML forecasting
- Third-party integrations beyond Monday.com

---

# 5. Functional Requirements

---

## 5.1 Monday.com Integration

- Use GraphQL API or MCP
- Read-only access
- Secure API token via environment variables
- Fetch:
  - Board schema
  - Items
  - Status fields
  - Dates
  - Numeric fields
- Handle pagination
- Retry transient failures

---

## 5.2 Data Resilience

The system must handle:

### Missing Values

- Null dates
- Missing revenue
- Missing sector
- Unlinked deals/work orders

Behavior:

- Replace safe numeric nulls with 0
- Exclude invalid rows when necessary
- Surface data caveats in responses

---

### Inconsistent Formats

Normalize:

- Revenue: "10k", "₹10000" → 10000
- Dates → ISO format
- Text → lowercase + trimmed
- Status values → mapped categories

---

## 5.3 Query Understanding

The agent must:

- Interpret vague business questions
- Map language to metrics
- Ask clarifying questions when necessary

Example:
“How are we doing?”  
→ Clarify: revenue, pipeline, or operations?

---

## 5.4 Business Intelligence Capabilities

### Revenue Analytics

- Closed revenue (time filtered)
- Revenue by sector
- Revenue by month/quarter

### Pipeline Health

- Total open pipeline value
- Pipeline by sector
- Weighted pipeline
- Deals closing this quarter

### Operational Metrics

- Active work orders
- Work orders by status
- Execution backlog
- Revenue per project

### Cross-Board Analysis

- Deal-to-work-order conversion rate
- Revenue realized vs pipeline
- Sector performance across sales & execution

---

## 5.5 Leadership Update Feature

Upon request, generate structured executive summaries:

Example:

Leadership Update – Current Quarter

- Total Pipeline: ₹X
- Energy Sector Share: X%
- Closed Revenue: ₹X
- Conversion Rate: X%
- Active Work Orders: X
- Operational Risk: Low / Medium / High
- Data Caveats: Summary

---

# 6. Non-Functional Requirements

## Performance

- <5 second response time (excluding API latency)

## Security

- API token stored securely
- No credential logging
- Read-only permissions

## Reliability

- Handle:
  - API timeouts
  - Invalid tokens
  - Missing boards
- Clear error messages

---

# 7. System Architecture

User  
↓  
Chat Interface  
↓  
Backend API  
↓  
Monday.com API  
↓  
Data Cleaning Layer  
↓  
Analytics Engine  
↓  
LLM Insight Generator  
↓  
Response

---

# 8. Data Processing Pipeline

1. Fetch board schema & items
2. Normalize data
3. Validate missing fields
4. Cross-board linking
5. Compute metrics
6. Generate insights
7. Surface caveats

---

# 9. Assumptions

- Deals board contains revenue & sector
- Work Orders board contains status & revenue
- At least one identifier links both boards
- API rate limits manageable

---

# 10. Definition of Done

The system is complete when:

- Data is dynamically fetched
- Cross-board analysis works
- Messy data is handled gracefully
- Contextual insights are generated
- Hosted prototype is accessible
- Documentation is complete
