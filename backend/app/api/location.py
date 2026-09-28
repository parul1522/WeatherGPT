from fastapi import APIRouter, Query

router = APIRouter()


@router.get("")
async def location_root(
    lat: float = Query(...),
    lon: float = Query(...),
):
    return {
        "module": "location",
        "location": {
            "latitude": lat,
            "longitude": lon
        },
        "message": "Location endpoint is working"
    }