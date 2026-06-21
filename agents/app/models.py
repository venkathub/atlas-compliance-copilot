"""Request/response models for the agent run API (P4_SPEC §2.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Start an agent run for the forcing-story query."""

    query: str = Field(..., min_length=1)
    account: str = Field(..., min_length=1)
    period: str = Field(..., pattern=r"^[0-9]{4}-Q[1-4]$")


class ResumeRequest(BaseModel):
    """The human approval decision that unlocks (or declines) a paused run."""

    approved: bool
    note: str | None = None


class Citation(BaseModel):
    n: int
    documentId: str | None = None
    clearance: str | None = None
    snippet: str | None = None


class ProposedAction(BaseModel):
    tool: str
    args: dict


class RunResponse(BaseModel):
    """Run state (shape per §2.3). Populated by the graph in task 7+."""

    runId: str
    status: str  # AWAITING_APPROVAL | COMPLETED | REJECTED | FAILED
    answer: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    proposedAction: ProposedAction | None = None
    action: dict | None = None
    auditRef: str | None = None
    trace: list[dict] = Field(default_factory=list)
