from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, utils

app = FastAPI(openapi_url=False, docs_url=False, redoc_url=False, swagger_ui_oauth2_redirect_url=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.router.include_router(auth.router)
app.router.include_router(utils.router)