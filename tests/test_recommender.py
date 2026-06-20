from __future__ import annotations

from stashai.core.models import RecommendationCategory
from stashai.core.repository import upsert_scene
from stashai.ml.recommender import RecommendationEngine


def _scene(scene_id: str, rating100: int | None, tag: str, performer: str, play_count: int = 0):
    return {
        "id": scene_id,
        "title": f"Scene {scene_id}",
        "rating100": rating100,
        "organized": False,
        "play_count": play_count,
        "created_at": "2026-01-01T00:00:00Z",
        "last_viewed_at": None,
        "duration": 1000,
        "scene_markers_count": 0,
        "studio": {"id": f"s-{tag}", "name": f"Studio {tag}"},
        "tags": [{"id": f"t-{tag}", "name": tag}],
        "performers": [{"id": f"p-{performer}", "name": performer}],
        "galleries": [],
        "files": [{"id": f"f-{scene_id}", "size": 1000, "width": 1280, "height": 720}],
    }


def test_recommendations_include_explanations(session, tmp_path):
    payloads = [
        _scene("liked-1", 100, "liked", "alice", 5),
        _scene("liked-2", 80, "liked", "alice", 4),
        _scene("bad-1", 20, "bad", "bob", 0),
        _scene("bad-2", 40, "bad", "bob", 0),
        _scene("candidate", None, "liked", "alice", 0),
        _scene("remove", None, "bad", "bob", 0),
    ]
    for payload in payloads:
        upsert_scene(session, payload)
    session.commit()

    engine = RecommendationEngine(str(tmp_path), recommendation_threshold=0.55, removal_threshold=0.55)
    outputs = engine.generate(session)

    by_scene = {output.scene_id: output for output in outputs}
    assert by_scene["candidate"].category in {RecommendationCategory.RECOMMENDED, RecommendationCategory.REVIEW}
    assert by_scene["candidate"].explanation
    assert by_scene["remove"].category == RecommendationCategory.LIKELY_REMOVE
    assert "low rated" in by_scene["remove"].explanation.lower() or "never viewed" in by_scene["remove"].explanation.lower()


def test_similar_scenes(session, tmp_path):
    for payload in [
        _scene("1", 100, "same", "alice"),
        _scene("2", None, "same", "alice"),
        _scene("3", None, "other", "bob"),
    ]:
        upsert_scene(session, payload)
    session.commit()

    engine = RecommendationEngine(str(tmp_path))
    similar = engine.similar_scenes(session, "1", limit=1)

    assert similar == [{"scene_id": "2", "score": 1.0}]

