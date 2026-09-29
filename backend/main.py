"""CTQ backend entry point.

Run:  uvicorn main:app --reload --port 8000   (from the backend/ directory)
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.cohort import cohort_router
from api.results_export import results_export_router
from api.routes import router
from api.samples import samples_router
from config import BACKEND_DIR
from services import database
from services.trial_retrieval import load_trials

app = FastAPI(
    title="CTQ - Clinical Trial Qualifier",
    description="AI-assisted clinical trial matching and eligibility analysis for Indian patients.",
    version="1.0.0",
)

# Vite dev server origins (any localhost port, so the dev server can fall
# back to another port when 5173 is busy)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(cohort_router)
app.include_router(results_export_router)
app.include_router(samples_router)

# ---------------------------------------------------------------------------
# Serve the built frontend (frontend/dist) from this same origin, so a single
# URL (localhost:8000 or a public share link) delivers both app and API with
# no CORS involved. Mounting after include_router lets /api routes win.
# ---------------------------------------------------------------------------
from fastapi.staticfiles import StaticFiles

FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
if (FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


@app.on_event("startup")
def startup() -> None:
    database.init_db()
    load_trials()  # imports data/trials.json into SQLite on first run


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never leak stack traces to the frontend (spec §49)."""
    print(f"[error] {request.method} {request.url.path}: {exc!r}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error. Please try again."})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
