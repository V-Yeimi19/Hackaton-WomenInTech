"""DTOs de reportes semanales."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel


class ReportPreviewRequest(BaseModel):
    cutoff_at: AwareDatetime | None = None
    kind: Literal["AUTO", "PRELIMINARY", "WEEKLY_FINAL"] = "AUTO"


class ReportOut(BaseModel):
    report_id: UUID
    environment: str
    kind: str
    period_start: AwareDatetime
    period_end: AwareDatetime
    data_cutoff_at: AwareDatetime
    revision: int
    rules_version: str
    metrics: dict[str, str]
    quality: dict
    primary_alert: str | None = None
    advice_code: str | None = None
    opportunity: dict
    text: str


class ReportResponse(BaseModel):
    report: ReportOut
    revisions: list[int]


class ReportListResponse(BaseModel):
    report: ReportOut | None
    revisions: list[int]
    message: str | None = None
