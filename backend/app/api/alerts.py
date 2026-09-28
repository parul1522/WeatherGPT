from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def alerts_root(
    lat: float = 23.2599,
    lon: float = 77.4126,
):
    return {
        "module": "alerts",
        "location": {
            "latitude": lat,
            "longitude": lon
        },
        "alerts": [],
        "message": "No active alerts"
    }