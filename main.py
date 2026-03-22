from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import sys, os

print("Reconfigurate imports and system path to Backend.")
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from routers import auth, utils, files, python_executor
    print("Paths to routers configured.")
except ImportError as e:
    print(f"Error importing routers: {e}")

app = FastAPI(openapi_url=False, docs_url=False, redoc_url=False, swagger_ui_oauth2_redirect_url=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/status")
def status():
    return {"status": "active"}

app.router.include_router(auth.router)
app.router.include_router(utils.router)
app.router.include_router(files.router)
app.router.include_router(python_executor.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7901, reload=False)