from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(StrictModel):
    document_id: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=1000)


class Requirement(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    kind: Literal[
        "material_presence",
        "file_format",
        "file_size",
        "page_count",
        "required_field",
        "field_consistency",
        "date_constraint",
        "semantic_requirement",
        "manual_review",
    ]
    document_type: str = Field(default="", max_length=100)
    required: bool = True
    condition: dict = Field(default_factory=dict)
    parameters: dict = Field(default_factory=dict)
    source_evidence: list[Evidence] = Field(min_length=1, max_length=10)
    explanation: str = Field(default="", max_length=1000)


class FieldCoverage(StrictModel):
    document_id: str
    field: str
    status: Literal["covered", "missing", "unreadable", "ambiguous", "invalid"]
    values: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class MaterialMatch(StrictModel):
    document_id: str
    status: Literal["verified", "unverified", "unreadable"]
    reason: str
    evidence: list[Evidence] = Field(default_factory=list)


class Finding(StrictModel):
    requirement_id: str
    applicability: Literal["applicable", "not_applicable", "unknown"] = "applicable"
    verdict: Literal["pass", "fail", "missing", "conflict", "unknown"]
    method: Literal["deterministic", "semantic", "manual"] = "deterministic"
    reason: str = Field(min_length=1, max_length=2000)
    next_action: str = Field(default="", max_length=1000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)
    dependencies: list[str] = Field(default_factory=list)
    field_coverage: list[FieldCoverage] = Field(default_factory=list)
    material_matches: list[MaterialMatch] = Field(default_factory=list)


class CaseInput(StrictModel):
    scenario_id: str | None = Field(default=None, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    institution: str = Field(default="", max_length=200)
    kind: str = Field(default="exchange", max_length=50)
    deadline: str = Field(default="", max_length=30)


class TextInput(StrictModel):
    title: str = Field(min_length=1, max_length=250)
    text: str = Field(min_length=1, max_length=200000)
    purpose: Literal["source", "material"] = "source"
    category: str = Field(default="", max_length=100)


class RevisionInput(StrictModel):
    revision: int


class ChatInput(RevisionInput):
    text: str = Field(min_length=1, max_length=10000)


class FactInput(RevisionInput):
    facts: dict[str, str | int | bool] = Field(max_length=30)


class RulesInput(RevisionInput):
    requirements: list[Requirement] = Field(min_length=1, max_length=80)
