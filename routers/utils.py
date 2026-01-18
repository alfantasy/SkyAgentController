from fastapi import APIRouter, Depends

from modules.auth import verify_access

import base64, io
from PIL import Image

router = APIRouter(
    prefix='/api/utils',
    tags=['Utils']
)

@router.get("/monitors")
async def get_monitors(token: str = Depends(verify_access)):
    ...

@router.post("/screenshot")
async def make_an_screenshot():
    pass