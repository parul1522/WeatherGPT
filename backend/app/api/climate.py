from fastapi import APIRouter, Query

router = APIRouter()


@router.get("")
async def climate_root(
    lat: float = Query(...),
    lon: float = Query(...),
):
    return {
        "module": "climate",
        "location": {
            "latitude": lat,
            "longitude": lon
        },
        "message": "Climate data endpoint is working"
    }
