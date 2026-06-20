from __future__ import annotations

from stashai.core.models import Scene
from stashai.core.repository import get_scene, upsert_scene


def test_upsert_scene_normalizes_stash_payload(session):
    upsert_scene(
        session,
        {
            "id": "1",
            "title": "Example",
            "rating100": 80,
            "organized": True,
            "play_count": 2,
            "created_at": "2026-01-02T00:00:00Z",
            "last_viewed_at": "2026-01-03T00:00:00Z",
            "duration": 1200,
            "scene_markers_count": 3,
            "studio": {"id": "s1", "name": "Studio"},
            "tags": [{"id": "t1", "name": "Tag"}],
            "performers": [{"id": "p1", "name": "Performer"}],
            "galleries": [{"id": "g1", "title": "Gallery"}],
            "files": [{"id": "f1", "size": 1000, "width": 1920, "height": 1080}],
        },
    )
    session.commit()

    scene = get_scene(session, "1")

    assert isinstance(scene, Scene)
    assert scene.rating == 4
    assert scene.organized is True
    assert scene.studio.name == "Studio"
    assert [tag.name for tag in scene.tags] == ["Tag"]
    assert [performer.name for performer in scene.performers] == ["Performer"]
    assert scene.file_size == 1000

