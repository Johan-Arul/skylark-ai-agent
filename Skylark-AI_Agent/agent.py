"""
agent.py
Skylark BI Agent — LLM integration and query orchestration.
Uses Groq (Llama 3.3 70B) for fast, free inference.
"""

import os
import json
import logging
from datetime import datetime, date
from typing import Optional
from dotenv import load_dotenv

from groq import Groq

from monday_client import MondayClient, MondayAPIError
from data_cleaner import (
    clean_deals_df,
    clean_workorders_df,
    compute_caveats,
    format_caveats_text,
)
from analytics import (
    revenue_analytics,
    pipeline_health,
    operational_metrics,
    cross_board_analysis,
    generate_leadership_update,
    format_leadership_update,
    _current_quarter_bounds,
)
from prompts import (
    SYSTEM_PROMPT,
    INTENT_CLASSIFIER_PROMPT,
    CLARIFICATION_TEMPLATES,
    LEADERSHIP_UPDATE_INSTRUCTION,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_current_quarter_label() -> str:
    """Return readable quarter label like 'Q1 FY2026 (Apr–Jun 2026)'."""
    today = date.today()
    q = (today.month - 1) // 3 + 1
    # Financial year quarter
    if today.month >= 4:
        fy = today.year + 1
        fq = (today.month - 4) // 3 + 1
    else:
        fy = today.year
        fq = (today.month + 8) // 3
    q_names = {1: "Apr–Jun", 2: "Jul–Sep", 3: "Oct–Dec", 4: "Jan–Mar"}
    return f"Q{fq} FY{fy} ({q_names[fq]} {today.year if today.month < 4 else today.year})"


class SkylarkAgent:
    """
    Main AI agent that orchestrates data fetching, cleaning, analytics,
    and LLM-powered response generation.
    """

    def __init__(self):
        groq_key = os.getenv("GROQ_API_KEY", "")
        if not groq_key:
            self.groq_client = None
            self._llm_error = (
                "⚠️ **No API key configured.**\n\n"
                "Add your free Groq key to the `.env` file:\n"
                "```\nGROQ_API_KEY=your_key_here\n```\n"
                "Get a free key at [console.groq.com](https://console.groq.com), then restart the server."
            )
            logger.warning("⚠️ GROQ_API_KEY not set — chat will show setup instructions.")
        else:
            self.groq_client = Groq(api_key=groq_key)
            self._llm_error = None
            logger.info("✅ LLM: Groq (llama-3.3-70b-versatile)")

        # Initialize Monday.com client
        self.monday = MondayClient()
        self.deals_board_id = os.getenv("DEALS_BOARD_ID", "")
        self.wo_board_id = os.getenv("WORKORDERS_BOARD_ID", "")

        # Data cache
        self.deals_df = None
        self.workorders_df = None
        self.caveats = {}
        self.analytics_cache = {}
        self.last_refresh = None

        # Pre-compute analytics context string
        self._analytics_context_str = ""

    def refresh_data(self) -> dict:
        """
        Fetch and clean data from both Monday.com boards.
        Returns summary of records loaded.
        """
        logger.info("Refreshing data from Monday.com...")
        result = {}

        # Fetch Deals board
        if self.deals_board_id:
            try:
                deals_schema, deals_raw = self.monday.get_board_data(self.deals_board_id)
                self.deals_df = clean_deals_df(deals_raw, deals_schema)
                result["deals_loaded"] = len(self.deals_df)
                logger.info(f"Loaded {len(self.deals_df)} deals")
            except MondayAPIError as e:
                logger.error(f"Failed to load deals: {e}")
                result["deals_error"] = str(e)
                self.deals_df = None
        else:
            result["deals_error"] = "DEALS_BOARD_ID not configured."

        # Fetch Work Orders board
        if self.wo_board_id:
            try:
                wo_schema, wo_raw = self.monday.get_board_data(self.wo_board_id)
                self.workorders_df = clean_workorders_df(wo_raw, wo_schema)
                result["workorders_loaded"] = len(self.workorders_df)
                logger.info(f"Loaded {len(self.workorders_df)} work orders")
            except MondayAPIError as e:
                logger.error(f"Failed to load work orders: {e}")
                result["workorders_error"] = str(e)
                self.workorders_df = None
        else:
            result["workorders_error"] = "WORKORDERS_BOARD_ID not configured."

        # Compute caveats + analytics cache
        if self.deals_df is not None and self.workorders_df is not None:
            self.caveats = compute_caveats(self.deals_df, self.workorders_df)
            self._build_analytics_context()

        self.last_refresh = datetime.now()
        return result

    def _build_analytics_context(self):
        """Pre-compute all analytics and serialize to a context string for injecting into LLM."""
        if self.deals_df is None or self.workorders_df is None:
            self._analytics_context_str = "No data available yet."
            return

        try:
            rev = revenue_analytics(self.deals_df, period="ytd")
            pipe = pipeline_health(self.deals_df, period="this_quarter")
            ops = operational_metrics(self.workorders_df)
            cross = cross_board_analysis(self.deals_df, self.workorders_df)
            leadership = generate_leadership_update(self.deals_df, self.workorders_df, self.caveats)

            self.analytics_cache = {
                "revenue_ytd": rev,
                "pipeline_this_quarter": pipe,
                "operations": ops,
                "cross_board": cross,
                "leadership_update": leadership,
                "caveats": self.caveats,
            }

            # Serialize cleanly for LLM context
            summary_lines = [
                f"=== LIVE DATA SUMMARY ===",
                f"Data refreshed: {self.last_refresh.strftime('%d %b %Y %H:%M') if self.last_refresh else 'Not yet'}",
                f"Total Deals: {len(self.deals_df)} | Open: {len(self.deals_df[self.deals_df['status']=='Open'])} | Won: {len(self.deals_df[self.deals_df['status']=='Won'])} | Dead: {len(self.deals_df[self.deals_df['status']=='Dead'])}",
                f"Total Work Orders: {len(self.workorders_df)} | Active: {ops.get('active_count',0)} | Completed: {ops.get('completed_count',0)}",
                "",
                f"=== PIPELINE (This Quarter) ===",
                f"Total Open Pipeline: {pipe.get('pipeline_total_fmt','N/A')}",
                f"Weighted Pipeline: {pipe.get('weighted_pipeline_fmt','N/A')}",
                f"Deals Closing This Quarter: {pipe.get('closing_this_quarter_count',0)} worth {pipe.get('closing_this_quarter_value','N/A')}",
                f"High Probability: {pipe.get('high_prob_pipeline','N/A')}",
                f"By Sector: {json.dumps(pipe.get('by_sector',{}))}",
                "",
                f"=== REVENUE (YTD) ===",
                f"Closed Revenue (YTD): {rev.get('closed_total_fmt','N/A')}",
                f"Won Deals Count: {rev.get('count',0)}",
                f"Top Sector: {rev.get('top_sector','N/A')} ({rev.get('top_sector_pct',0)}%)",
                f"By Sector: {json.dumps(rev.get('by_sector',{}))}",
                "",
                f"=== OPERATIONS ===",
                f"Active Work Orders: {ops.get('active_count',0)}",
                f"Backlog (Unbilled): {ops.get('backlog_value','N/A')}",
                f"Operational Risk: {ops.get('operational_risk','N/A')} — {ops.get('risk_note','')}",
                f"By Status: {json.dumps(ops.get('by_status',{}))}",
                "",
                f"=== CROSS-BOARD ===",
                f"Deal Win Rate: {cross.get('conversion_rate_pct',0)}%",
                f"Won → Work Order Coverage: {cross.get('wo_coverage_rate_pct',0)}%",
                f"Total WO Value: {cross.get('total_wo_value','N/A')}",
                "",
                f"=== DATA CAVEATS ===",
                format_caveats_text(self.caveats) or "No significant data quality issues.",
            ]
            self._analytics_context_str = "\n".join(summary_lines)

        except Exception as e:
            logger.error(f"Error building analytics context: {e}")
            self._analytics_context_str = f"Analytics computation error: {e}"

    def _was_last_clarification(self, history: list) -> bool:
        """Return True if the most recent assistant message was a clarification question."""
        for msg in reversed(history):
            if msg.get("role") in ("assistant", "model"):
                content = msg.get("content", "")
                # Clarification messages contain these characteristic phrases
                return (
                    "do you mean:" in content.lower()
                    or "could you clarify" in content.lower()
                    or "when you say" in content.lower()
                    or "are you asking" in content.lower()
                )
        return False

    def _llm_generate(self, prompt: str, history: list = None) -> str:
        """
        Call Groq with optional multi-turn history.
        history: list of {role, content} dicts.
        """
        if not self.groq_client:
            raise RuntimeError("GROQ_API_KEY not configured.")

        messages = []
        if history:
            for m in history[-10:]:
                messages.append({
                    "role": m.get("role", "user"),
                    "content": m.get("content", ""),
                })
        messages.append({"role": "user", "content": prompt})

        resp = self.groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )
        return resp.choices[0].message.content.strip()

    def _classify_intent(self, query: str, history: list = None) -> str:
        """Use LLM to classify query intent into a routing category."""
        try:
            # Build a mini conversation context for the classifier
            context_snippet = ""
            if history:
                recent = history[-4:]  # last 2 turns max
                lines = []
                for m in recent:
                    role = "User" if m.get("role") == "user" else "Agent"
                    lines.append(f"{role}: {m.get('content', '')[:200]}")
                context_snippet = "\n".join(lines)

            prompt = INTENT_CLASSIFIER_PROMPT.format(
                query=query,
                context=context_snippet if context_snippet else "(no prior conversation)",
            )
            intent = self._llm_generate(prompt)
            intent = intent.strip().lower().split()[0]  # take first word only
            valid = {"revenue", "pipeline", "operations", "crossboard", "leadership", "general", "ambiguous"}
            return intent if intent in valid else "general"  # default to general, not ambiguous
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return "general"  # fail open — always try to answer

    def _build_system_prompt(self) -> str:
        """Build the final system prompt with live analytics injected."""
        today = datetime.now().strftime("%d %B %Y")
        quarter = _get_current_quarter_label()
        return SYSTEM_PROMPT.format(
            today_date=today,
            current_quarter=quarter,
            analytics_context=self._analytics_context_str,
        )

    def answer(self, query: str, conversation_history: list = None) -> dict:
        """
        Main entry point: takes a user query and returns a structured response.
        Returns: {response, intent, caveats_text, used_data}
        """
        if conversation_history is None:
            conversation_history = []

        # Show setup instructions if no LLM is configured
        if self._llm_error:
            return {
                "response": self._llm_error,
                "intent": "ambiguous",
                "caveats": "",
                "used_data": False,
            }

        # If the previous agent message was a clarification, treat the current reply
        # as the user's answer — skip re-classification and go straight to the LLM.
        # This prevents the clarification loop bug.
        if self._was_last_clarification(conversation_history):
            logger.info("Previous turn was a clarification — forwarding answer to LLM directly.")
            intent = self._infer_intent_from_clarification_context(conversation_history)
        else:
            # Normal intent classification with context
            intent = self._classify_intent(query, conversation_history)
        logger.info(f"Intent: {intent} | Query: {query[:80]}")

        # Handle ambiguous queries — only ask for clarification if query is truly
        # off-topic (no dataset relevance). Otherwise fall through to general answering.
        if intent == "ambiguous":
            if self._was_last_clarification(conversation_history):
                intent = "general"  # already clarified — just answer
            else:
                clarification = self._get_clarification(query)
                return {
                    "response": clarification,
                    "intent": "ambiguous",
                    "caveats": "",
                    "used_data": False,
                }

        # Handle leadership update specially
        if intent == "leadership":
            return self._generate_leadership_response()

        # All other intents (revenue, pipeline, operations, crossboard, general)
        # go straight to the LLM with full analytics context.
        # This means ANY question about the dataset is answered freely.
        # Ensure data is loaded
        if self.deals_df is None and self.workorders_df is None:
            return {
                "response": (
                    "⚠️ I don't have Monday.com data loaded yet. "
                    "Please configure your `MONDAY_API_TOKEN`, `DEALS_BOARD_ID`, and `WORKORDERS_BOARD_ID` "
                    "in the `.env` file, then restart the server."
                ),
                "intent": intent,
                "caveats": "",
                "used_data": False,
            }

        # Build full prompt with system context
        system_prompt = self._build_system_prompt()
        full_prompt = f"{system_prompt}\n\n---\n\nUser question: {query}"

        try:
            answer_text = self._llm_generate(full_prompt, history=self._format_history(conversation_history))
            caveats_text = format_caveats_text(self.caveats)

            return {
                "response": answer_text,
                "intent": intent,
                "caveats": caveats_text,
                "used_data": True,
            }

        except Exception as e:
            logger.error(f"LLM error: {e}")
            return {
                "response": f"⚠️ I encountered an error generating your response. Please try again.\n\nError: {str(e)}",
                "intent": intent,
                "caveats": "",
                "used_data": False,
            }

    def _generate_leadership_response(self) -> dict:
        """Generate the leadership update report."""
        if self.deals_df is None or self.workorders_df is None:
            return {
                "response": "⚠️ Cannot generate leadership update — Monday.com data not loaded. Please configure your API credentials.",
                "intent": "leadership",
                "caveats": "",
                "used_data": False,
            }

        try:
            update = generate_leadership_update(self.deals_df, self.workorders_df, self.caveats)
            md = format_leadership_update(update)

            # Let LLM add insights on top of the structured data
            insight_prompt = f"{self._build_system_prompt()}\n\n{LEADERSHIP_UPDATE_INSTRUCTION}\n\nHere is the pre-computed data:\n\n{md}\n\nProduce the final leadership update with your added insights and observations."
            answer_text = self._llm_generate(insight_prompt)
            return {
                "response": answer_text,
                "intent": "leadership",
                "caveats": format_caveats_text(self.caveats),
                "used_data": True,
            }
        except Exception as e:
            logger.error(f"Leadership update error: {e}")
            # Fall back to pure analytics-derived response
            update = generate_leadership_update(self.deals_df, self.workorders_df, self.caveats)
            return {
                "response": format_leadership_update(update),
                "intent": "leadership",
                "caveats": format_caveats_text(self.caveats),
                "used_data": True,
            }

    def _infer_intent_from_clarification_context(self, history: list) -> str:
        """Infer a non-ambiguous intent when the user has answered a clarification."""
        # Look at the original question (the last user message before the clarification)
        for i, msg in enumerate(reversed(history)):
            if msg.get("role") == "user":
                q = msg.get("content", "").lower()
                if any(w in q for w in ["revenue", "income", "billed", "closed", "pipeline"]):
                    return "revenue"
                if any(w in q for w in ["work order", "operation", "execution", "active", "backlog"]):
                    return "operations"
                if any(w in q for w in ["convert", "conversion", "win rate", "cross"]):
                    return "crossboard"
                if any(w in q for w in ["pipeline", "open deal", "stage"]):
                    return "pipeline"
        return "revenue"  # safe fallback

    def _get_clarification(self, query: str) -> str:
        """Return an appropriate clarification question for an ambiguous query."""
        q = query.lower()
        if any(w in q for w in ["doing", "status", "overall", "update", "how are"]):
            return CLARIFICATION_TEMPLATES["how_are_we_doing"]
        if "revenue" in q or "income" in q or "money" in q:
            return CLARIFICATION_TEMPLATES["revenue_ambiguous"]
        if any(w in q for w in ["when", "period", "time", "month", "quarter"]):
            return CLARIFICATION_TEMPLATES["time_ambiguous"]
        return CLARIFICATION_TEMPLATES["generic"]

    def _format_history(self, history: list) -> list:
        """Convert conversation history to Groq chat format (user / assistant roles)."""
        formatted = []
        for msg in history[-10:]:  # Keep last 10 messages for context
            raw_role = msg.get("role", "user")
            # Normalise: Gemini uses 'model', frontend may send 'assistant' — Groq wants 'user' or 'assistant'
            role = "user" if raw_role == "user" else "assistant"
            content = msg.get("content", "")
            if content:  # Skip empty messages — Groq rejects them
                formatted.append({"role": role, "content": content})
        return formatted

    def get_status(self) -> dict:
        """Return agent health and data status."""
        return {
            "status": "ok",
            "data_loaded": self.deals_df is not None or self.workorders_df is not None,
            "deals_count": len(self.deals_df) if self.deals_df is not None else 0,
            "workorders_count": len(self.workorders_df) if self.workorders_df is not None else 0,
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "monday_configured": bool(self.deals_board_id and self.wo_board_id),
        }
