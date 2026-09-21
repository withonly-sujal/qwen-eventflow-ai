import sys
import os
import contextlib
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import config
from . import mcp_client as mcp
from . import agent

# Global state to hold the active MCP session
app_state = {}

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the MCP session
    try:
        config.validate()
        print("[...] Connecting to Solace MCP Server, please wait...")
        # Since managed_session is an async generator, we use it directly
        # but we need to hold it open for the lifespan.
        async with mcp.managed_session() as session:
            app_state["session"] = session
            print("[OK] Connected — Smart Router Active.")
            yield
    except Exception as exc:
        print(f"\n[ERROR] Failed to connect to Solace MCP Server: {exc}")
        sys.exit(1)
    finally:
        # Shutdown
        app_state.clear()

app = FastAPI(lifespan=lifespan)

class ChatRequest(BaseModel):
    prompt: str
    persona: Optional[str] = "admin"

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Read the HTML prototype file
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, "BackStage", "Backstage-EventFlow-Assistant-prototype.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/chat")
async def chat(request: ChatRequest):
    session = app_state.get("session")
    if not session:
        return {"error": "MCP session not initialized"}
    
    try:
        # Run the agent with the user's prompt
        response = await agent.run(request.prompt, session, request.persona)
        # Format it slightly to match the UI expectation (convert newlines to <br>, strip markdown asterisks)
        formatted = response.replace("*", "").replace("\n", "<br>")
        return {"response": formatted}
    except Exception as exc:
        return {"error": str(exc)}
