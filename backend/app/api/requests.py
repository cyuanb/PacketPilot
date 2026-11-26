"""HTTP request models supplementing the shared domain schemas."""

from pydantic import BaseModel, Field

from ..schemas import CaseInput, RevisionInput


class LoginInput(BaseModel):
    username: str = Field(max_length=80)
    password: str = Field(max_length=200)


class CaseUpdate(CaseInput):
    revision: int
    archived: bool = False


class CorrectionInput(BaseModel):
    text: str = Field(min_length=1, max_length=200000)
    revision: int


class AttestationInput(RevisionInput):
    requirement_id: str
    note: str = Field(min_length=1, max_length=1000)
