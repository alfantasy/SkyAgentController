from fastapi import APIRouter

router = APIRouter(
    prefix='/api/utils',
    tags=['Utils']
)

@router.post("/screenshot")
async def make_an_screenshot():
    pass