from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AlertServiceDep, RequestedLocationDep
from app.database.connection import get_db
from app.schemas.alert import AlertResponse

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get(
    "",
    response_model=AlertResponse,
    summary="Official alerts for a location, plus optional app-generated advisories",
)
async def get_alerts(
    location: RequestedLocationDep,
    service: AlertServiceDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_advisories: Annotated[
        bool, Query(description="Also return rule-based advisories derived from the forecast (not official)")
    ] = False,
) -> AlertResponse:
    return await service.get_alerts(location, db, include_advisories=include_advisories)
