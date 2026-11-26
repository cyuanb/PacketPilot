from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ..schemas import RevisionInput, StrictModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Role = Literal["applicant", "recommender", "representative", "organization", "contact", "other"]
ATTRIBUTE_KEYS = {
    "person": {"email", "phone", "affiliation"},
    "organization": {"registration_number", "contact_email", "contact_phone"},
}


class WorkspaceUpdate(RevisionInput):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class SubjectInput(StrictModel):
    kind: Literal["person", "organization"]
    name: Name
    label: str = Field(default="", max_length=200)
    attributes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_attributes(self):
        if set(self.attributes) - ATTRIBUTE_KEYS[self.kind]:
            raise ValueError("主体字段不属于此档案类型")
        if any(len(value) > 300 for value in self.attributes.values()):
            raise ValueError("主体字段不能超过 300 个字符")
        self.label = self.label.strip()
        self.attributes = {key: value.strip() for key, value in self.attributes.items()}
        return self


class SubjectUpdate(SubjectInput):
    revision: int = Field(ge=1)
    archived: bool = False


class SubjectLink(StrictModel):
    subject_id: str = Field(min_length=1, max_length=36)
    role: Role


class CaseSubjectsInput(RevisionInput):
    links: list[SubjectLink] = Field(max_length=50)
