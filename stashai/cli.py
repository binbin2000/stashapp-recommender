from __future__ import annotations

import argparse
import asyncio
import os

import uvicorn

from stashai.core.config import ensure_runtime_dirs, load_settings
from stashai.core.database import init_db, make_session_factory
from stashai.services import generate_recommendations, sync_from_stash


def main() -> None:
    parser = argparse.ArgumentParser(prog="stashai")
    parser.add_argument("--config", default=None)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init-db")
    subcommands.add_parser("sync")
    subcommands.add_parser("recommend")
    subcommands.add_parser("run")
    args = parser.parse_args()

    settings = load_settings(args.config)
    ensure_runtime_dirs(settings)
    init_db(settings.database.url)
    session_factory = make_session_factory(settings.database.url)

    if args.command == "init-db":
        print("Database initialized")
    elif args.command == "sync":
        result = asyncio.run(sync_from_stash(settings, session_factory))
        print(f"Synced {result.scenes_synced} scenes")
    elif args.command == "recommend":
        count = generate_recommendations(settings, session_factory)
        print(f"Generated {count} recommendations")
    elif args.command == "run":
        if args.config:
            os.environ["STASHAI_CONFIG"] = args.config
        uvicorn.run("stashai.web.app:create_app", factory=True, host=settings.app.host, port=settings.app.port)
