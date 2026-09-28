from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

from app.routes import snomed_route
from app.routes import cohort_route
from app.services import cohort_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    cohort_worker.start_workers()
    yield
    cohort_worker.stop_workers()


app = FastAPI(lifespan=lifespan)

# API routes
app.include_router(snomed_route.router, prefix="/api")
app.include_router(cohort_route.router, prefix="/api")


# Path to the React production build
frontend_build_path = os.path.join(
    os.path.dirname(__file__),
    "../frontend/build"
)


if os.path.exists(frontend_build_path):

    # Serve React static assets
    app.mount(
        "/static",
        StaticFiles(
            directory=os.path.join(frontend_build_path, "static")
        ),
        name="static"
    )

    # Serve the Cohort Builder user manual
    app.mount(
        "/manual",
        StaticFiles(
            directory=os.path.join(frontend_build_path, "manual")
        ),
        name="manual"
    )

    # Serve the React app for all other frontend routes
    @app.get("/{path_name:path}")
    async def serve_react_app(path_name: str):
        return FileResponse(
            os.path.join(frontend_build_path, "index.html")
        )

else:
    print(
        "Warning: React build folder not found. "
        "Run 'npm run build' in the frontend directory."
    )