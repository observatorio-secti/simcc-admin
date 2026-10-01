from fastapi import APIRouter

from simcc_admin.routers.academic import institutions, researchers

router = APIRouter(prefix="/academic")

router.include_router(institutions.router)
router.include_router(researchers.router)
