# StashAI Recommender

Local-first recommendation system for StashApp. It syncs scene metadata through Stash GraphQL, stores AI-generated data separately, trains local scikit-learn models, and exposes a small FastAPI dashboard.

## Safety Model

- The app never deletes scenes.
- The app never modifies Stash metadata automatically.
- Synced Stash metadata, recommendations, and feedback are stored locally in SQLite.
- Future Stash tag write-back is intentionally outside the initial implementation and should require explicit user action.

## Quick Start

```bash
cp config.example.yaml config.yaml
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
stashai init-db
stashai sync
stashai recommend
stashai run
```

Open `http://localhost:8088`.

## Configuration

Edit `config.yaml`:

```yaml
stash:
  url: "http://localhost:9999/graphql"
  api_key: null
  page_size: 100

database:
  url: "sqlite:///./data/stashai.sqlite3"

models:
  directory: "./models"
```

If your Stash instance requires an API key, set `stash.api_key`.

## Commands

```bash
stashai init-db       # create local tables
stashai sync          # pull scene metadata from Stash
stashai recommend     # train local models and generate queues
stashai run           # start the dashboard
```

## Docker

```bash
cp config.example.yaml config.yaml
docker compose up --build
```

The dashboard is exposed on `http://localhost:8088`.

To run the published GHCR image:

```bash
docker pull ghcr.io/binbin2000/stashapp-recommender:latest
docker compose up
```

The compose file uses `ghcr.io/binbin2000/stashapp-recommender:latest` and can also build locally from this repository.

## GHCR Publishing

GitHub Actions builds and publishes the Docker image on pushes to `main`, version tags like `v0.1.0`, and manual workflow dispatches. Pull requests build the image without pushing.

Published image:

```text
ghcr.io/binbin2000/stashapp-recommender
```

## Architecture

- `stashai/stash`: GraphQL client and synchronization engine.
- `stashai/core`: configuration, SQLAlchemy schema, repositories.
- `stashai/ml`: feature engineering, TF-IDF similarity, logistic regression preference model, removal scoring.
- `stashai/web`: FastAPI dashboard and API routes.
- `stashai/services.py`: orchestration layer used by CLI and web routes.

The web dashboard is a thin layer over the engine. A future Stash plugin can call the same service/API layer and remain a UI shell.

## Recommendation Methods

1. Similarity engine: TF-IDF over tags, performers, and studios.
2. Preference prediction: logistic regression from local historical ratings when enough labels exist.
3. Removal review score: low predicted enjoyment, similarity to disliked scenes, never viewed, and low engagement.

Each generated recommendation includes a score, confidence, and human-readable explanation.

## Feedback

Scene detail pages support:

- Keep
- Remove Candidate
- Recommended
- Not Recommended
- Wrong Suggestion

Feedback is stored locally and included as a feature in future training runs.

## Tests

```bash
pytest
```
