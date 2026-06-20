from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from stashai.core.database import Base


scene_tags = Table(
    "scene_tags",
    Base.metadata,
    Column("scene_id", ForeignKey("scenes.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)

scene_performers = Table(
    "scene_performers",
    Base.metadata,
    Column("scene_id", ForeignKey("scenes.id"), primary_key=True),
    Column("performer_id", ForeignKey("performers.id"), primary_key=True),
)

scene_galleries = Table(
    "scene_galleries",
    Base.metadata,
    Column("scene_id", ForeignKey("scenes.id"), primary_key=True),
    Column("gallery_id", ForeignKey("galleries.id"), primary_key=True),
)


class RecommendationCategory(StrEnum):
    RECOMMENDED = "recommended"
    REVIEW = "review"
    LIKELY_REMOVE = "likely_remove"


class FeedbackAction(StrEnum):
    KEEP = "keep"
    REMOVE_CANDIDATE = "remove_candidate"
    RECOMMENDED = "recommended"
    NOT_RECOMMENDED = "not_recommended"
    WRONG_SUGGESTION = "wrong_suggestion"


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    organized: Mapped[bool] = mapped_column(Boolean, default=False)
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    date_added: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    marker_count: Mapped[int] = mapped_column(Integer, default=0)
    studio_id: Mapped[str | None] = mapped_column(ForeignKey("studios.id"), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    studio: Mapped["Studio | None"] = relationship(back_populates="scenes")
    tags: Mapped[list["Tag"]] = relationship(secondary=scene_tags, back_populates="scenes")
    performers: Mapped[list["Performer"]] = relationship(secondary=scene_performers, back_populates="scenes")
    galleries: Mapped[list["Gallery"]] = relationship(secondary=scene_galleries, back_populates="scenes")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="scene", cascade="all, delete-orphan")
    feedback: Mapped[list["Feedback"]] = relationship(back_populates="scene", cascade="all, delete-orphan")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scenes: Mapped[list[Scene]] = relationship(secondary=scene_tags, back_populates="tags")


class Performer(Base):
    __tablename__ = "performers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scenes: Mapped[list[Scene]] = relationship(secondary=scene_performers, back_populates="performers")


class Studio(Base):
    __tablename__ = "studios"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scenes: Mapped[list[Scene]] = relationship(back_populates="studio")


class Gallery(Base):
    __tablename__ = "galleries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scenes: Mapped[list[Scene]] = relationship(secondary=scene_galleries, back_populates="galleries")


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("scene_id", "category", name="uq_scene_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id"), index=True)
    category: Mapped[RecommendationCategory] = mapped_column(Enum(RecommendationCategory), index=True)
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text, default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String, default="local-v1")

    scene: Mapped[Scene] = relationship(back_populates="recommendations")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id"), index=True)
    action: Mapped[FeedbackAction] = mapped_column(Enum(FeedbackAction), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scene: Mapped[Scene] = relationship(back_populates="feedback")
