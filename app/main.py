"""FastAPI application entry point for Prompt 1."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.logging_config import configure_logging
from app.routes.planner import router as planner_router


configure_logging()
app = FastAPI(title="HeatShield X", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(planner_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
