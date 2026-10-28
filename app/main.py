from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

from app.routes import snomed_route
from app.routes import cohort_route
from app.services import cohort_worker

import fcntl
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):

    os.makedirs(settings.queue_data_path, exist_ok=True)

    lock_path = os.path.join(
        settings.queue_data_path,
        "cohort_worker.lock"
    )

    lock_file = open(lock_path, "a+")

    try:
        try:
            fcntl.flock(
                lock_file,
                fcntl.LOCK_EX | fcntl.LOCK_NB
            )
            is_manager = True

        except BlockingIOError:
            is_manager = False

        if is_manager:
            print(
                f">>> PID {os.getpid()}: QUEUE MANAGER",
                flush=True
            )
            cohort_worker.start_workers()
        else:
            print(
                f">>> PID {os.getpid()}: API ONLY",
                flush=True
            )
            cohort_worker.initialise_queue(auto_resume=False)

        try:
            yield
        finally:
            if is_manager:
                cohort_worker.stop_workers()

    finally:
        lock_file.close()


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