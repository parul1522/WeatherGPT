from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import GeocodingServiceDep
from app.schemas.location import Location

router = APIRouter(prefix="/location", tags=["Location"])


@router.get("/geocode", response_model=Location, summary="Find coordinates for a place name")
async def geocode(
    service: GeocodingServiceDep,
    query: Annotated[
        str,
        Query(min_length=2, max_length=100, description="Place name, optionally with state/country: 'Bhopal, India'"),
    ],
    language: Annotated[str, Query(pattern=r"^[a-z]{2}$", description="Language for place names")] = "en",
) -> Location:
    return await service.geocode(query, language)
