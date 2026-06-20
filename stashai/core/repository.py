from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from stashai.core.models import (
    Feedback,
    FeedbackAction,
    Gallery,
    Performer,
    Recommendation,
    RecommendationCategory,
    Scene,
    Studio,
    Tag,
)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def _get_or_create(session: Session, model, item_id: str, **values):
    for pending in session.new:
        if isinstance(pending, model) and pending.id == item_id:
            for key, value in values.items():
                setattr(pending, key, value)
            return pending

    instance = session.get(model, item_id)
    if instance is None:
        instance = model(id=item_id, **values)
        session.add(instance)
    else:
        for key, value in values.items():
            setattr(instance, key, value)
    return instance


def upsert_scene(session: Session, data: dict[str, Any]) -> Scene:
    scene = session.get(Scene, str(data["id"]))
    if scene is None:
        scene = Scene(id=str(data["id"]))
        session.add(scene)

    files = data.get("files") or []
    primary_file = files[0] if files else {}
    studio_data = data.get("studio")
    studio = None
    if studio_data:
        studio = _get_or_create(session, Studio, str(studio_data["id"]), name=studio_data.get("name") or "")

    scene.title = data.get("title") or ""
    scene.rating = data.get("rating100")
    if scene.rating is not None:
        scene.rating = round(scene.rating / 20)
    scene.organized = bool(data.get("organized"))
    scene.play_count = int(data.get("play_count") or 0)
    scene.date_added = _parse_dt(data.get("created_at") or data.get("date"))
    scene.last_viewed_at = _parse_dt(data.get("last_viewed_at"))
    scene.duration = data.get("duration")
    scene.width = primary_file.get("width")
    scene.height = primary_file.get("height")
    scene.file_size = primary_file.get("size")
    markers = data.get("scene_markers")
    scene.marker_count = len(markers) if markers is not None else int(data.get("scene_markers_count") or 0)
    scene.studio = studio
    scene.synced_at = datetime.utcnow()

    scene.tags = [
        _get_or_create(session, Tag, str(tag["id"]), name=tag.get("name") or "")
        for tag in data.get("tags") or []
    ]
    scene.performers = [
        _get_or_create(session, Performer, str(performer["id"]), name=performer.get("name") or "")
        for performer in data.get("performers") or []
    ]
    scene.galleries = [
        _get_or_create(session, Gallery, str(gallery["id"]), title=gallery.get("title") or "")
        for gallery in data.get("galleries") or []
    ]
    return scene


def list_scenes(session: Session) -> list[Scene]:
    stmt = (
        select(Scene)
        .options(
            joinedload(Scene.tags),
            joinedload(Scene.performers),
            joinedload(Scene.galleries),
            joinedload(Scene.studio),
        )
        .order_by(Scene.title)
    )
    return list(session.scalars(stmt).unique())


def get_scene(session: Session, scene_id: str) -> Scene | None:
    stmt = (
        select(Scene)
        .where(Scene.id == scene_id)
        .options(
            joinedload(Scene.tags),
            joinedload(Scene.performers),
            joinedload(Scene.galleries),
            joinedload(Scene.studio),
            joinedload(Scene.recommendations),
            joinedload(Scene.feedback),
        )
    )
    return session.scalars(stmt).unique().first()


def replace_recommendations(session: Session, recommendations: list[dict[str, Any]]) -> None:
    session.execute(delete(Recommendation))
    for rec in recommendations:
        session.add(Recommendation(**rec))


def recommendations_by_category(
    session: Session, category: RecommendationCategory, limit: int = 100
) -> list[Recommendation]:
    stmt = (
        select(Recommendation)
        .where(Recommendation.category == category)
        .options(joinedload(Recommendation.scene).joinedload(Scene.tags))
        .options(joinedload(Recommendation.scene).joinedload(Scene.performers))
        .order_by(Recommendation.score.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).unique())


def add_feedback(session: Session, scene_id: str, action: FeedbackAction, notes: str = "") -> Feedback:
    feedback = Feedback(scene_id=scene_id, action=action, notes=notes)
    session.add(feedback)
    return feedback


def overview_counts(session: Session) -> dict[str, int]:
    total = session.scalar(select(func.count(Scene.id))) or 0
    rated = session.scalar(select(func.count(Scene.id)).where(Scene.rating.is_not(None))) or 0
    recommended = session.scalar(
        select(func.count(Recommendation.id)).where(Recommendation.category == RecommendationCategory.RECOMMENDED)
    ) or 0
    review = session.scalar(
        select(func.count(Recommendation.id)).where(Recommendation.category == RecommendationCategory.REVIEW)
    ) or 0
    likely_remove = session.scalar(
        select(func.count(Recommendation.id)).where(Recommendation.category == RecommendationCategory.LIKELY_REMOVE)
    ) or 0
    return {
        "total_scenes": total,
        "rated_scenes": rated,
        "training_coverage": round((rated / total) * 100) if total else 0,
        "recommended": recommended,
        "review": review,
        "likely_remove": likely_remove,
    }
