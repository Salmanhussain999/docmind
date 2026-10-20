import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .db import init_db
from .embeddings import Embedder, create_embedder
from .llm import AnswerGenerator, create_generator
from .retrieval import Retriever, VectorIndex
from .routes import chat, documents
from .schemas import HealthOut

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(
    settings: Settings | None = None,
    embedder: Embedder | None = None,
    generator: AnswerGenerator | None = None,
) -> FastAPI:
    """
    Builds the app. Run with `uvicorn app.main:create_app --factory`; tests pass their own
    settings, embedder and generator.
    """
    settings = settings or get_settings()
    init_db(settings.db_path)

    app = FastAPI(title="DocMind", version="1.0.0", description="Chat with your documents.")
    app.state.settings = settings
    app.state.embedder = embedder or create_embedder(settings)
    app.state.index = VectorIndex(settings.db_path)
    app.state.retriever = Retriever(settings.db_path, app.state.embedder, app.state.index)
    app.state.generator = generator or create_generator(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health", response_model=HealthOut, tags=["meta"])
    def health(request: Request) -> HealthOut:
        state = request.app.state
        return HealthOut(
            status="ok",
            answer_mode=state.generator.mode,
            model=state.generator.model,
            embeddings=f"{state.embedder.name}",
        )

    app.include_router(documents.router)
    app.include_router(chat.router)

    # In production the API also serves the built React app, so it deploys as one service.
    if settings.web_dist_dir:
        dist = Path(settings.web_dist_dir)
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False, response_model=None)
        def spa(path: str) -> FileResponse | JSONResponse:
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
                return FileResponse(candidate)
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return app
