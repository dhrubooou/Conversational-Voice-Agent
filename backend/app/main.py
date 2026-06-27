import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.init_db import initialize_database
from app.api.router import api_router
from app.api.endpoints.websocket import router as ws_router

# 1. Setup Structured JSON Logging
setup_logging()

# 2. Instantiate FastAPI Application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-grade End-to-End Conversational Voice Agent Platform",
    version="1.0.0",
)

# 3. Enable Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 4. Initialize Database Schema and Tables on Startup
@app.on_event("startup")
def on_startup():
    print("🚀 Bootstrapping database system...")
    initialize_database()


# 5. Include API v1 REST Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# 6. Include WebSocket Routing (Direct mounting)
app.include_router(ws_router, prefix=f"{settings.API_V1_STR}/ws")

if __name__ == "__main__":
    # Start FastAPI Application
    # Use the package module path so the reloader can import the app correctly
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
