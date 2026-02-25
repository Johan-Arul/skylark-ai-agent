import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import SkylarkAgent
from monday_client import MondayAPIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[list[ChatMessage]] = []


class ChatResponse(BaseModel):
    response: str
    intent: str
    caveats: str
    used_data: bool


class RefreshResponse(BaseModel):
    message: str
    details: dict


# ──────────────────────────────────────────────
# App lifecycle
# ──────────────────────────────────────────────

agent: SkylarkAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the agent on startup and load Monday.com data."""
    global agent
    logger.info("🚀 Starting Skylark BI Agent...")

    try:
        agent = SkylarkAgent()
        logger.info("✅ Agent initialized with Gemini")

        # Initial data load (non-blocking on error — API might not be configured yet)
        try:
            result = agent.refresh_data()
            logger.info(f"📊 Data loaded: {result}")
        except MondayAPIError as e:
            logger.warning(f"⚠️ Monday.com data not loaded on startup: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Data load skipped: {e}")

    except ValueError as e:
        logger.error(f"❌ Agent init failed: {e}")
        # Continue anyway — show config instructions to user
        agent = None

    yield
    logger.info("👋 Skylark BI Agent shutting down.")


# ──────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────

app = FastAPI(
    title="Skylark BI Agent API",
    description="Monday.com Business Intelligence Agent for Skylark Drones",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_frontend():
    """Serve the chat UI frontend."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content=_fallback_ui())


@app.get("/health")
async def health_check():
    """Agent health and data status endpoint."""
    if agent is None:
        return {
            "status": "error",
            "message": "Agent not initialized. Check GEMINI_API_KEY in .env file.",
        }
    return agent.get_status()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    Accepts a user message and optional conversation history.
    Returns the agent's response with intent classification and data caveats.
    """
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Agent not initialized. "
                "Please set GEMINI_API_KEY in your .env file and restart."
            ),
        )

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    history = [{"role": m.role, "content": m.content} for m in (request.conversation_history or [])]

    try:
        result = agent.answer(request.message, history)
        return ChatResponse(
            response=result["response"],
            intent=result["intent"],
            caveats=result.get("caveats", ""),
            used_data=result.get("used_data", False),
        )
    except MondayAPIError as e:
        raise HTTPException(status_code=502, detail=f"Monday.com API error: {str(e)}")
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/leadership-update", response_model=ChatResponse)
async def leadership_update():
    """Generate a structured executive leadership update report."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized.")

    result = agent.answer("Give me the full leadership update for this quarter")
    return ChatResponse(
        response=result["response"],
        intent="leadership",
        caveats=result.get("caveats", ""),
        used_data=result.get("used_data", False),
    )


@app.post("/refresh", response_model=RefreshResponse)
async def refresh_data():
    """
    Manually trigger a Monday.com data refresh.
    Call this when you know data has been updated.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized.")

    try:
        result = agent.refresh_data()
        return RefreshResponse(
            message="✅ Data refreshed successfully from Monday.com",
            details=result,
        )
    except MondayAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _fallback_ui() -> str:
    """Minimal fallback HTML if frontend folder not found."""
    return """
    <!DOCTYPE html><html><head><title>Skylark BI Agent</title></head>
    <body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#eee">
    <h1>🚁 Skylark BI Agent</h1>
    <p>Frontend not found. API is running at <a href="/docs" style="color:#7c83fd">/docs</a></p>
    <p>Create the <code>frontend/</code> folder with <code>index.html</code>.</p>
    </body></html>
    """


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    # On cloud (Railway/Render) we must bind to 0.0.0.0; locally use 127.0.0.1
    host = "0.0.0.0" if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER") else "127.0.0.1"
    uvicorn.run("app:app", host=host, port=port, reload=False)
