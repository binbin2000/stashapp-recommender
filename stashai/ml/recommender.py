from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from stashai.core.models import RecommendationCategory
from stashai.ml.features import FeatureSet, build_feature_set


NUMERIC_FEATURES = [
    "duration",
    "width",
    "height",
    "resolution_pixels",
    "file_size",
    "play_count",
    "marker_count",
    "organized",
    "days_since_added",
    "days_since_viewed",
    "performer_popularity",
    "studio_popularity",
    "tag_frequency",
    "feedback_score",
]


@dataclass(frozen=True)
class RecommendationOutput:
    scene_id: str
    category: RecommendationCategory
    score: float
    confidence: float
    explanation: str
    model_version: str = "local-v1"


@dataclass
class TrainedModels:
    classifier: Pipeline | None
    vectorizer: TfidfVectorizer
    tfidf_matrix: Any
    scene_ids: list[str]
    liked_indices: list[int]
    disliked_indices: list[int]


class RecommendationEngine:
    def __init__(
        self,
        model_dir: str,
        positive_threshold: int = 4,
        negative_threshold: int = 2,
        recommendation_threshold: float = 0.70,
        review_confidence_threshold: float = 0.35,
        removal_threshold: float = 0.65,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.positive_threshold = positive_threshold
        self.negative_threshold = negative_threshold
        self.recommendation_threshold = recommendation_threshold
        self.review_confidence_threshold = review_confidence_threshold
        self.removal_threshold = removal_threshold

    def train(self, session: Session) -> TrainedModels:
        features = build_feature_set(session)
        if features.frame.empty:
            return self._empty_models()

        vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w:.-]+\b")
        tfidf_matrix = vectorizer.fit_transform(features.text)
        frame = features.frame.copy()
        labeled = frame[frame["rating"].notna()].copy()
        labeled = labeled[(labeled["rating"] >= self.positive_threshold) | (labeled["rating"] <= self.negative_threshold)]

        classifier = None
        if len(labeled) >= 4 and labeled["rating"].nunique() >= 2:
            y = (labeled["rating"] >= self.positive_threshold).astype(int)
            classifier = Pipeline(
                steps=[
                    ("preprocess", ColumnTransformer([("numeric", StandardScaler(), NUMERIC_FEATURES)])),
                    ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
                ]
            )
            classifier.fit(labeled[NUMERIC_FEATURES], y)

        liked_indices = [
            idx for idx, rating in enumerate(frame["rating"].tolist()) if rating is not None and rating >= self.positive_threshold
        ]
        disliked_indices = [
            idx for idx, rating in enumerate(frame["rating"].tolist()) if rating is not None and rating <= self.negative_threshold
        ]
        trained = TrainedModels(
            classifier=classifier,
            vectorizer=vectorizer,
            tfidf_matrix=tfidf_matrix,
            scene_ids=frame["scene_id"].astype(str).tolist(),
            liked_indices=liked_indices,
            disliked_indices=disliked_indices,
        )
        self.model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(trained, self.model_dir / "recommender.joblib")
        return trained

    def generate(self, session: Session) -> list[RecommendationOutput]:
        features = build_feature_set(session)
        if features.frame.empty:
            return []
        trained = self.train(session)
        frame = features.frame.reset_index(drop=True)
        enjoy_probs = self._predict_enjoyment(trained, frame)
        liked_similarity = self._max_similarity(trained, trained.liked_indices)
        disliked_similarity = self._max_similarity(trained, trained.disliked_indices)

        outputs: list[RecommendationOutput] = []
        for idx, row in frame.iterrows():
            rating = row["rating"]
            if rating is not None and not pd.isna(rating):
                continue
            enjoy_prob = float(enjoy_probs[idx])
            liked_sim = float(liked_similarity[idx])
            disliked_sim = float(disliked_similarity[idx])
            confidence = min(1.0, abs(enjoy_prob - 0.5) * 2 * 0.7 + max(liked_sim, disliked_sim) * 0.3)
            removal_score = self._removal_score(enjoy_prob, liked_sim, disliked_sim, row)

            if removal_score >= self.removal_threshold:
                outputs.append(
                    RecommendationOutput(
                        scene_id=str(row["scene_id"]),
                        category=RecommendationCategory.LIKELY_REMOVE,
                        score=removal_score,
                        confidence=confidence,
                        explanation=self._removal_explanation(disliked_sim, row),
                    )
                )
            elif enjoy_prob >= self.recommendation_threshold and confidence >= self.review_confidence_threshold:
                outputs.append(
                    RecommendationOutput(
                        scene_id=str(row["scene_id"]),
                        category=RecommendationCategory.RECOMMENDED,
                        score=enjoy_prob,
                        confidence=confidence,
                        explanation=self._recommended_explanation(liked_sim, row),
                    )
                )
            else:
                outputs.append(
                    RecommendationOutput(
                        scene_id=str(row["scene_id"]),
                        category=RecommendationCategory.REVIEW,
                        score=enjoy_prob,
                        confidence=confidence,
                        explanation=self._review_explanation(enjoy_prob, confidence),
                    )
                )
        return outputs

    def similar_scenes(self, session: Session, scene_id: str, limit: int = 10) -> list[dict[str, Any]]:
        features = build_feature_set(session)
        if features.frame.empty or scene_id not in set(features.frame["scene_id"].astype(str)):
            return []
        vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w:.-]+\b")
        matrix = vectorizer.fit_transform(features.text)
        scene_ids = features.frame["scene_id"].astype(str).tolist()
        idx = scene_ids.index(scene_id)
        scores = cosine_similarity(matrix[idx], matrix).ravel()
        matches = [
            {"scene_id": scene_ids[i], "score": float(np.clip(scores[i], 0.0, 1.0))}
            for i in np.argsort(scores)[::-1]
            if i != idx
        ]
        return matches[:limit]

    def _empty_models(self) -> TrainedModels:
        vectorizer = TfidfVectorizer()
        return TrainedModels(None, vectorizer, None, [], [], [])

    def _predict_enjoyment(self, trained: TrainedModels, frame: pd.DataFrame) -> np.ndarray:
        if trained.classifier is None:
            base = np.full(len(frame), 0.5)
            if trained.liked_indices:
                base += self._max_similarity(trained, trained.liked_indices) * 0.25
            if trained.disliked_indices:
                base -= self._max_similarity(trained, trained.disliked_indices) * 0.25
            return np.clip(base, 0.0, 1.0)
        return trained.classifier.predict_proba(frame[NUMERIC_FEATURES])[:, 1]

    def _max_similarity(self, trained: TrainedModels, indices: list[int]) -> np.ndarray:
        if trained.tfidf_matrix is None or not indices:
            return np.zeros(len(trained.scene_ids))
        sims = cosine_similarity(trained.tfidf_matrix, trained.tfidf_matrix[indices])
        return sims.max(axis=1)

    def _removal_score(
        self, enjoy_prob: float, liked_similarity: float, disliked_similarity: float, row: pd.Series
    ) -> float:
        never_viewed = 1.0 if int(row["play_count"]) == 0 and int(row["days_since_viewed"]) >= 9999 else 0.0
        low_engagement = 1.0 if int(row["play_count"]) <= 1 and int(row["marker_count"]) == 0 else 0.0
        raw_score = (1 - enjoy_prob) * 0.55 + disliked_similarity * 0.25 + never_viewed * 0.10 + low_engagement * 0.10
        score = raw_score * (1 - min(liked_similarity, 1.0) * 0.35)
        return float(np.clip(score, 0.0, 1.0))

    def _recommended_explanation(self, liked_similarity: float, row: pd.Series) -> str:
        reasons = []
        if liked_similarity > 0:
            reasons.append(f"Similar to highly rated scenes ({liked_similarity:.0%} content match)")
        if row["performer_names"]:
            reasons.append("Contains performers that appear often in the collection")
        if row["tag_names"]:
            reasons.append("Contains tags that appear frequently in the collection")
        return "; ".join(reasons) or "Predicted enjoyment score is high"

    def _removal_explanation(self, disliked_similarity: float, row: pd.Series) -> str:
        reasons = []
        if disliked_similarity > 0:
            reasons.append(f"Similar to low rated scenes ({disliked_similarity:.0%} content match)")
        if int(row["play_count"]) == 0:
            reasons.append("Never viewed")
        if int(row["marker_count"]) == 0:
            reasons.append("No markers recorded")
        return "; ".join(reasons) or "Predicted value is low"

    def _review_explanation(self, enjoy_prob: float, confidence: float) -> str:
        return f"Needs manual review because confidence is {confidence:.0%} with an enjoyment score of {enjoy_prob:.0%}"
