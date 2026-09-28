from fastapi import APIRouter

router = APIRouter()


@router.get("")
def weather_root():
    return {"module": "weather", "status": "todo"}
