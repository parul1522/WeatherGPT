from fastapi import APIRouter

router = APIRouter()


@router.get("")
def location_root():
    return {"module": "location", "status": "todo"}
