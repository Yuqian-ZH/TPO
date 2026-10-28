"""Request bodies. Unknown fields are rejected (extra="forbid"), so a client cannot slip anything else into a
session or a complaint; modifications are then checked against Task 3's whitelist by the service."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    routes: list[list[int]] = Field(min_length=1, max_length=10)


class CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: str | None = Field(None, description="One of the eight Task 3 configurations; default A0B0C1")
    label: str | None = Field(None, max_length=100)
    model_modifications: list[dict[str, Any]] = Field(default_factory=list, max_length=20,
                                                      description="Session data in Task 2's modification format")
    solution: Plan | None = Field(None, description="Initial plan; default: the optimal plan")
    max_iterations: int | None = Field(None, ge=1, le=3)


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    complaint: str = Field(min_length=1, max_length=2000)
    solution_version: int | None = Field(None, ge=0, description="The plan the complaint is about")
    solution: Plan | None = Field(None, description="Alternative to solution_version: the plan's routes")


class ClarificationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=2000)


class ReplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolved: bool
    comment: str | None = Field(None, max_length=2000, description="Fed back to TPO when not resolved")
    stop: bool = Field(False, description="Give up on this complaint; the plan returns to the one complained about")
