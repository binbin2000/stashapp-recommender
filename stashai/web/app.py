from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from stashai.core.config import ensure_runtime_dirs, load_settings
from stashai.core.database import init_db, make_session_factory
from stashai.core.models import FeedbackAction, RecommendationCategory
from stashai.core.repository import get_scene, overview_counts, recommendations_by_category
from stashai.ml.recommender import RecommendationEngine
from stashai.services import generate_recommendations, make_recommendation_engine, record_feedback, sync_from_stash


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app() -> FastAPI:
    settings = load_settings()
    ensure_runtime_dirs(settings)
    init_db(settings.database.url)
    session_factory = make_session_factory(settings.database.url)

    app = FastAPI(title="StashAI Recommender")
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    app.state.settings = settings
    app.state.session_factory = session_factory

    def get_session() -> Session:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def engine() -> RecommendationEngine:
        return make_recommendation_engine(settings)

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, session: Session = Depends(get_session)):
        counts = overview_counts(session)
        return templates.TemplateResponse(request, "dashboard.html", {"counts": counts})

    @app.post("/sync")
    async def sync():
        await sync_from_stash(settings, session_factory)
        return RedirectResponse("/", status_code=303)

    @app.post("/recommendations/generate")
    def generate():
        generate_recommendations(settings, session_factory)
        return RedirectResponse("/", status_code=303)

    @app.get("/recommendations/{category}", response_class=HTMLResponse)
    def recommendation_queue(category: RecommendationCategory, request: Request, session: Session = Depends(get_session)):
        items = recommendations_by_category(session, category)
        return templates.TemplateResponse(
            request,
            "queue.html",
            {"category": category, "items": items},
        )

    @app.get("/scenes/{scene_id}", response_class=HTMLResponse)
    def scene_detail(
        scene_id: str,
        request: Request,
        session: Session = Depends(get_session),
        recommendation_engine: RecommendationEngine = Depends(engine),
    ):
        scene = get_scene(session, scene_id)
        if scene is None:
            raise HTTPException(status_code=404, detail="Scene not found")
        similar = recommendation_engine.similar_scenes(session, scene_id)
        similar_scenes = [(get_scene(session, item["scene_id"]), item["score"]) for item in similar]
        return templates.TemplateResponse(
            request,
            "scene.html",
            {"scene": scene, "similar_scenes": similar_scenes},
        )

    @app.post("/scenes/{scene_id}/feedback")
    def feedback(scene_id: str, action: FeedbackAction = Form(...), notes: str = Form("")):
        record_feedback(session_factory, scene_id, action, notes)
        return RedirectResponse(f"/scenes/{scene_id}", status_code=303)

    @app.get("/api/overview")
    def api_overview(session: Session = Depends(get_session)):
        return overview_counts(session)

    return app
