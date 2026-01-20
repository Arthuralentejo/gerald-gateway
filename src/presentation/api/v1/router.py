from fastapi import APIRouter

from .decision import decision_router
from .plan import plan_router
from .health import health_router

router = APIRouter()

router.include_router(health_router, tags=["Health"])
router.include_router(decision_router, tags=["Decisions"])
router.include_router(plan_router, tags=["Plans"])
