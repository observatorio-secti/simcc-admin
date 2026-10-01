from fastapi import APIRouter

from simcc_admin.routers.academic import researchers

router = APIRouter(prefix="/academic")

router.include_router(researchers.router)
