from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from stashai.core.models import FeedbackAction, Scene
from stashai.core.repository import list_scenes


@dataclass(frozen=True)
class FeatureSet:
    frame: pd.DataFrame
    text: list[str]


def scene_text(scene: Scene) -> str:
    parts: list[str] = []
    parts.extend(f"tag:{tag.name}" for tag in scene.tags)
    parts.extend(f"performer:{performer.name}" for performer in scene.performers)
    if scene.studio:
        parts.append(f"studio:{scene.studio.name}")
    return " ".join(parts) or "unknown"


def build_feature_set(session: Session, now: datetime | None = None) -> FeatureSet:
    now = now or datetime.utcnow()
    scenes = list_scenes(session)
    performer_counts: dict[str, int] = {}
    studio_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    for scene in scenes:
        for performer in scene.performers:
            performer_counts[performer.id] = performer_counts.get(performer.id, 0) + 1
        for tag in scene.tags:
            tag_counts[tag.id] = tag_counts.get(tag.id, 0) + 1
        if scene.studio_id:
            studio_counts[scene.studio_id] = studio_counts.get(scene.studio_id, 0) + 1

    rows: list[dict[str, object]] = []
    texts: list[str] = []
    for scene in scenes:
        days_since_added = (now - scene.date_added).days if scene.date_added else 0
        days_since_viewed = (now - scene.last_viewed_at).days if scene.last_viewed_at else 9999
        performer_popularity = max((performer_counts.get(p.id, 0) for p in scene.performers), default=0)
        tag_frequency = max((tag_counts.get(t.id, 0) for t in scene.tags), default=0)
        feedback_score = _feedback_score(scene)
        rows.append(
            {
                "scene_id": scene.id,
                "rating": scene.rating,
                "duration": float(scene.duration or 0),
                "width": int(scene.width or 0),
                "height": int(scene.height or 0),
                "resolution_pixels": int(scene.width or 0) * int(scene.height or 0),
                "file_size": int(scene.file_size or 0),
                "play_count": int(scene.play_count or 0),
                "marker_count": int(scene.marker_count or 0),
                "organized": int(scene.organized),
                "days_since_added": max(days_since_added, 0),
                "days_since_viewed": max(days_since_viewed, 0),
                "performer_popularity": performer_popularity,
                "studio_popularity": studio_counts.get(scene.studio_id or "", 0),
                "tag_frequency": tag_frequency,
                "feedback_score": feedback_score,
                "tag_names": [tag.name for tag in scene.tags],
                "performer_names": [performer.name for performer in scene.performers],
                "studio_name": scene.studio.name if scene.studio else "",
            }
        )
        texts.append(scene_text(scene))
    return FeatureSet(pd.DataFrame(rows), texts)


def _feedback_score(scene: Scene) -> int:
    score = 0
    for feedback in scene.feedback:
        if feedback.action in {FeedbackAction.KEEP, FeedbackAction.RECOMMENDED}:
            score += 1
        elif feedback.action in {
            FeedbackAction.REMOVE_CANDIDATE,
            FeedbackAction.NOT_RECOMMENDED,
            FeedbackAction.WRONG_SUGGESTION,
        }:
            score -= 1
    return score

