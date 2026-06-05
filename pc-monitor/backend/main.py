import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from collector import get_all, get_system_info

app = FastAPI(title="PC Monitor")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/api/system")
async def system_info():
    return get_system_info()

# Mount static files AFTER specific routes
app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")

# Active WebSocket connections
connections: list[WebSocket] = []

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connections.append(ws)
    sort_by = 'cpu'
    try:
        # Start sending data
        while True:
            try:
                # Check for client messages (non-blocking)
                try:
                    msg = await asyncio.wait_for(ws.receive_text(), timeout=0.05)
                    data = json.loads(msg)
                    if 'sort_by' in data:
                        sort_by = data['sort_by']
                except asyncio.TimeoutError:
                    pass
                
                # Collect and send system data
                system_data = await asyncio.get_event_loop().run_in_executor(
                    None, get_all, sort_by
                )
                await ws.send_json(system_data)
                await asyncio.sleep(1)
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket error: {e}")
                break
    finally:
        if ws in connections:
            connections.remove(ws)

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  PC Monitor Dashboard")
    print("  http://localhost:8765")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
