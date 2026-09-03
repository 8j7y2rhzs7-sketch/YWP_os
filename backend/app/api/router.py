from fastapi import APIRouter

from app.api import auth, bankroll, errors, health, learning, protocols, sports, tickets, users, whop

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(bankroll.router)
api_router.include_router(protocols.router)
api_router.include_router(sports.router)
api_router.include_router(tickets.router)
api_router.include_router(learning.router)
api_router.include_router(errors.router)
api_router.include_router(whop.router)
