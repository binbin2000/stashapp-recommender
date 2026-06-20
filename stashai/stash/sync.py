from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from stashai.core.repository import upsert_scene
from stashai.stash.client import StashGraphQLClient


@dataclass(frozen=True)
class SyncResult:
    scenes_synced: int


class StashSynchronizer:
    def __init__(self, client: StashGraphQLClient, session_factory: sessionmaker, page_size: int = 100) -> None:
        self.client = client
        self.session_factory = session_factory
        self.page_size = page_size

    async def sync_scenes(self) -> SyncResult:
        count = 0
        session = self.session_factory()
        try:
            async for scene_data in self.client.iter_scenes(self.page_size):
                upsert_scene(session, scene_data)
                count += 1
                if count % 100 == 0:
                    session.commit()
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return SyncResult(scenes_synced=count)

