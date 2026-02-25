# 🚁 Skylark BI Agent

> Conversational AI Business Intelligence agent for Skylark Drones.  
> Ask founder-level questions about your Monday.com pipeline and work orders.

---

## Features

- **Live Monday.com integration** — fetches real-time data via GraphQL API
- **Smart data cleaning** — handles missing values, ₹ format variants, date parsing
- **Cross-board analytics** — links Deals → Work Orders for conversion metrics
- **Gemini 1.5 Flash LLM** — fast, contextual, founder-friendly responses
- **Leadership Update** — one-click structured executive summary
- **Premium chat UI** — dark glassmorphism design, mobile-responsive

---

## Quick Start

### 1. Clone / open project
```
cd Skylark-AI_Agent
```

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
copy .env.example .env
```
Edit `.env` and fill in:

| Key | Where to get it |
|---|---|
| `MONDAY_API_TOKEN` | Monday.com → Profile → Admin → API |
| `DEALS_BOARD_ID` | Open the Deals board → URL contains the board ID |
| `WORKORDERS_BOARD_ID` | Open the Work Orders board → URL |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key |

### 5. Run the server
```bash
python app.py
```
Or with auto-reload:
```bash
uvicorn app:app --reload --port 8000
```

### 6. Open in browser
```
http://localhost:8000
```

---

## Example Questions

- *"What is our total open pipeline this quarter?"*
- *"Show me revenue breakdown by sector"*
- *"Are we operationally overloaded?"*
- *"What is our deal-to-project conversion rate?"*
- *"Give me a leadership update"*

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Agent + data status |
| `POST` | `/chat` | Main chat endpoint |
| `POST` | `/leadership-update` | Executive summary report |
| `POST` | `/refresh` | Force Monday.com data reload |
| `GET` | `/docs` | Interactive API docs |

---

## Architecture

```
User → Chat UI → FastAPI → SkylarkAgent
                              ├── MondayClient (GraphQL)
                              ├── DataCleaner (Pandas)
                              ├── Analytics Engine
                              └── Gemini 1.5 Flash (LLM)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini 1.5 Flash |
| Backend | FastAPI + Uvicorn |
| Data | Pandas + Pydantic |
| Monday.com | GraphQL API (direct) |
| Frontend | Vanilla HTML/CSS/JS |

---

## Data Security

- API tokens stored in `.env` (never committed)
- Read-only Monday.com access
- No credentials in logs
- No data written back to Monday.com
