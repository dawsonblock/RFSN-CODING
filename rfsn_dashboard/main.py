"""RFSN Dashboard Backend.

Serves the UI, manages API keys, and broadcasts controller events via WebSockets.
"""

import os
import asyncio
import json
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

# Load existing environment
load_dotenv()

app = FastAPI(title="RFSN Dashboard")

# Allow CORS for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- State Management ---

class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Remove dead connections lazily
                pass

manager = ConnectionManager()

# --- Models ---

class ConfigUpdate(BaseModel):
    """Configuration update request."""
    DEEPSEEK_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None

class ControllerEvent(BaseModel):
    """Event received from the controller."""
    type: str  # e.g., "log", "step", "patch", "error"
    data: Dict
    run_id: Optional[str] = None

# --- Routes ---

@app.get("/api/config")
async def get_config():
    """Get current configuration (masked keys)."""
    # Reload env to get latest values
    load_dotenv(override=True)
    
    def mask(key: str) -> Optional[str]:
        val = os.getenv(key)
        if not val:
            return None
        if len(val) < 8:
            return "*" * len(val)
        return val[:4] + "*" * (len(val) - 8) + val[-4:]

    return {
        "DEEPSEEK_API_KEY": mask("DEEPSEEK_API_KEY"),
        "GEMINI_API_KEY": mask("GEMINI_API_KEY"),
        "OPENAI_API_KEY": mask("OPENAI_API_KEY"),
        "GITHUB_TOKEN": mask("GITHUB_TOKEN"),
    }

@app.post("/api/config")
async def update_config(config: ConfigUpdate):
    """Update API keys in .env file."""
    env_file = Path(".env")
    if not env_file.exists():
        env_file.touch()

    updates = config.dict(exclude_unset=True)
    updated_count = 0
    
    for key, value in updates.items():
        if value:
            # Write to .env file
            set_key(env_file, key, value)
            # Update current process env
            os.environ[key] = value
            updated_count += 1
            
    return {"status": "ok", "updated": updated_count}

@app.post("/api/events")
async def receive_event(event: ControllerEvent = Body(...)):
    """Receive an event from the controller and broadcast it."""
    # Add timestamp if missing
    msg = json.dumps({
        "type": event.type,
        "data": event.data,
        "run_id": event.run_id
    })
    await manager.broadcast(msg)
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for the frontend."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, maybe receive commands from UI later
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Serve static files (UI)
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Run on localhost:8000
    print("Starting RFSN Dashboard on http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
