from typing import Literal

from pydantic import BaseModel, Field


class CustomerAIRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    organization: str | None = None
    stage: Literal[
        "lead", "qualified", "proposal",
        "negotiation", "won", "lost"
    ] = "lead"
    notes: str | None = None


class CustomerAIResponse(BaseModel):
    summary: str
    suggested_action: str
    priority: Literal["low", "medium", "high"]
    generated_by: Literal["rules", "ai"] = "rules"