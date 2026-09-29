from fastapi import APIRouter, HTTPException, Query

from backend.app.services.climate_service import get_climate

router = APIRouter()


@router.get("")
def climate_root(
    lat: float = Query(...),
    lon: float = Query(...),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
):
    location = {"latitude": lat, "longitude": lon}

    if not (start_date and end_date):
        return {
            "module": "climate",
            "location": location,
            "message": (
                "Provide start_date and end_date (YYYY-MM-DD) "
                "for historical climate data."
            ),
        }

    try:
        data = get_climate(lat, lon, start_date, end_date)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    if "error" in data:
        raise HTTPException(status_code=502, detail=data["error"])

    return {"module": "climate", "location": location, **data}
