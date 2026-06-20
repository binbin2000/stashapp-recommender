from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx


SCENE_QUERY = """
query FindScenes($page: Int!, $per_page: Int!) {
  findScenes(scene_filter: {page: $page, per_page: $per_page, sort: "created_at", direction: DESC}) {
    count
    scenes {
      id
      title
      rating100
      organized
      play_count
      created_at
      date
      last_viewed_at
      duration
      scene_markers_count
      studio { id name }
      tags { id name }
      performers { id name }
      galleries { id title }
      scene_markers { id }
      files { id size width height }
    }
  }
}
"""


class StashGraphQLError(RuntimeError):
    pass


class StashGraphQLClient:
    def __init__(self, url: str, api_key: str | None = None, timeout: float = 30.0) -> None:
        self.url = url
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["ApiKey"] = self.api_key
        return headers

    async def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.url,
                headers=self._headers(),
                json={"query": query, "variables": variables or {}},
            )
            response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise StashGraphQLError(str(payload["errors"]))
        return payload["data"]

    async def iter_scenes(self, page_size: int = 100) -> AsyncIterator[dict[str, Any]]:
        page = 1
        seen = 0
        while True:
            data = await self.execute(SCENE_QUERY, {"page": page, "per_page": page_size})
            result = data["findScenes"]
            scenes = result.get("scenes") or []
            for scene in scenes:
                seen += 1
                yield scene
            if not scenes or seen >= int(result.get("count") or 0):
                break
            page += 1
