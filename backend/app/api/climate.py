from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import RequestedLocationDep, get_climate_service, get_date_range
from app.schemas.climate import ClimateDateRange, ClimateResponse
from app.services.climate_service import ClimateService

router = APIRouter(prefix="/climate", tags=["Climate"])


@router.get(
    "/history",
    response_model=ClimateResponse,
    summary="Historical daily weather with monthly and period summaries (max 366 days)",
)
async def climate_history(
    location: RequestedLocationDep,
    date_range: Annotated[ClimateDateRange, Depends(get_date_range)],
    service: Annotated[ClimateService, Depends(get_climate_service)],
) -> ClimateResponse:
    return await service.get_history(location, date_range)
