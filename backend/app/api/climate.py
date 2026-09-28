from fastapi import APIRouter

router = APIRouter()


@router.get("")
def climate_root():
    return {"module": "climate", "status": "todo"}
