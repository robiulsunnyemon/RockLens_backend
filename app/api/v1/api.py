from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, specimens, identification

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(specimens.router)
api_router.include_router(identification.router)

