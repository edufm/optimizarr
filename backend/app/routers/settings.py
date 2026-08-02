from __future__ import annotations

from fastapi import APIRouter

from .. import state
from ..models import Settings

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings() -> Settings:
    return Settings(**state.get_settings())


@router.put("/settings")
def update_settings(body: Settings) -> Settings:
    updated = state.update_settings(body.model_dump())
    return Settings(**updated)
