from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from stashai.core.config import Settings
from stashai.core.models import FeedbackAction
from stashai.core.repository import add_feedback, replace_recommendations
from stashai.ml.recommender import RecommendationEngine
from stashai.stash.client import StashGraphQLClient
from stashai.stash.sync import StashSynchronizer, SyncResult


def make_recommendation_engine(settings: Settings) -> RecommendationEngine:
    return RecommendationEngine(
        model_dir=settings.models.directory,
        positive_threshold=settings.models.positive_rating_threshold,
        negative_threshold=settings.models.negative_rating_threshold,
        recommendation_threshold=settings.models.recommendation_threshold,
        review_confidence_threshold=settings.models.review_confidence_threshold,
        removal_threshold=settings.models.removal_threshold,
    )


async def sync_from_stash(settings: Settings, session_factory: sessionmaker) -> SyncResult:
    client = StashGraphQLClient(settings.stash.url, settings.stash.api_key)
    synchronizer = StashSynchronizer(client, session_factory, settings.stash.page_size)
    return await synchronizer.sync_scenes()


def generate_recommendations(settings: Settings, session_factory: sessionmaker) -> int:
    engine = make_recommendation_engine(settings)
    session = session_factory()
    try:
        outputs = engine.generate(session)
        replace_recommendations(
            session,
            [
                {
                    "scene_id": output.scene_id,
                    "category": output.category,
                    "score": output.score,
                    "confidence": output.confidence,
                    "explanation": output.explanation,
                    "model_version": output.model_version,
                }
                for output in outputs
            ],
        )
        session.commit()
        return len(outputs)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def record_feedback(session_factory: sessionmaker, scene_id: str, action: FeedbackAction, notes: str = "") -> None:
    session = session_factory()
    try:
        add_feedback(session, scene_id, action, notes)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

