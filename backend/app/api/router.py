from fastapi import APIRouter
from app.api.endpoints import config, token, session, twilio

api_router = APIRouter()

# Include REST Routers
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(token.router, prefix="/token", tags=["token"])
api_router.include_router(session.router, prefix="/session", tags=["session"])
api_router.include_router(twilio.router, prefix="/twilio", tags=["twilio"])
