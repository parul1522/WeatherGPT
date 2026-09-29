from fastapi import APIRouter

from backend.app.services.alert_service import get_alerts

router = APIRouter()


@router.get("")
def alerts_root(
    lat: float = 23.2599,
    lon: float = 77.4126,
    location: str | None = None,
):
    """Official IMD alerts. ``location`` is the city name used to look up the
    configured IMD district (see IMD_DISTRICT_IDS in .env.example)."""

    return get_alerts(lat=lat, lon=lon, location=location)
