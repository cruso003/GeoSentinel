"""Model-registry schemas (Phase 2.4 §5)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

STAGE = Literal["candidate", "staging", "production", "archived"]


class ModelVersionIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=128)
    metrics: dict[str, Any]
    data_sha256: str | None = Field(default=None, max_length=64)
    artifact_uri: str | None = Field(default=None, max_length=500)
    mlflow_run_id: str | None = Field(default=None, max_length=64)


class ModelVersionOut(BaseModel):
    id: str
    name: str
    version: str
    stage: STAGE
    data_sha256: str | None
    metrics: dict[str, Any]
    artifact_uri: str | None
    mlflow_run_id: str | None
    created_at: datetime
    promoted_at: datetime | None
    promoted_by: str | None

    @classmethod
    def from_row(cls, row) -> ModelVersionOut:
        return cls(
            id=row.id,
            name=row.name,
            version=row.version,
            stage=row.stage,
            data_sha256=row.data_sha256,
            metrics=json.loads(row.metrics_json or "{}"),
            artifact_uri=row.artifact_uri,
            mlflow_run_id=row.mlflow_run_id,
            created_at=row.created_at,
            promoted_at=row.promoted_at,
            promoted_by=row.promoted_by,
        )


class PromoteRequest(BaseModel):
    force: bool = False


class PromoteResponse(BaseModel):
    promoted: bool
    gate: dict
    version: ModelVersionOut
