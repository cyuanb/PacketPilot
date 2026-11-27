from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, now, uid


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200))
    institution: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(50), default="exchange")
    deadline: Mapped[str] = mapped_column(String(30), default="")
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Shanghai")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    active_rules_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    current_check_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    facts: Mapped[dict] = mapped_column(JSONB, default=dict)
    scenario_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_cases_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "owner_id"],
            ["workspaces.id", "workspaces.owner_id"],
            name="fk_cases_workspace_owner",
        ),
    )


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(100), default="个人工作空间")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("id", "owner_id", name="uq_workspace_owner"),)


class Membership(Base):
    __tablename__ = "memberships"
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="owner")
    __table_args__ = (CheckConstraint("role = 'owner'", name="ck_membership_owner_only"),)


class SubjectProfile(Base):
    __tablename__ = "subject_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    label: Mapped[str] = mapped_column(String(200), default="")
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_subject_workspace"),
        CheckConstraint("kind IN ('person', 'organization')", name="ck_subject_kind"),
    )


class CaseSubjectRole(Base):
    __tablename__ = "case_subject_roles"
    case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    role: Mapped[str] = mapped_column(String(30), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "workspace_id"],
            ["cases.id", "cases.workspace_id"],
            ondelete="CASCADE",
            name="fk_role_case_workspace",
        ),
        ForeignKeyConstraint(
            ["subject_id", "workspace_id"],
            ["subject_profiles.id", "subject_profiles.workspace_id"],
            name="fk_role_subject_workspace",
        ),
        CheckConstraint(
            "role IN ('applicant', 'recommender', 'representative', 'organization', 'contact', 'other')",
            name="ck_subject_role",
        ),
    )


class Document(Base):
    __tablename__ = "document_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    asset_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("asset_revisions.id"), nullable=True, index=True
    )
    logical_id: Mapped[str] = mapped_column(String(36), default=uid, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    title: Mapped[str] = mapped_column(String(250))
    purpose: Mapped[str] = mapped_column(String(20), default="material")
    category: Mapped[str] = mapped_column(String(100), default="")
    filename: Mapped[str] = mapped_column(String(250), default="")
    storage_key: Mapped[str] = mapped_column(String(100), default="")
    sha256: Mapped[str] = mapped_column(String(64), default="")
    mime: Mapped[str] = mapped_column(String(100), default="text/plain")
    size: Mapped[int] = mapped_column(Integer, default=0)
    parse_status: Mapped[str] = mapped_column(String(30), default="queued")
    pages: Mapped[list] = mapped_column(JSONB, default=list)
    parse_note: Mapped[str] = mapped_column(Text, default="")
    parse_method: Mapped[str] = mapped_column(String(40), default="native")
    current_parse_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assignment: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("logical_id", "version"),
        UniqueConstraint("id", "case_id", name="uq_document_case"),
        UniqueConstraint("id", "asset_revision_id", name="uq_document_asset_revision"),
    )


class RuleSet(Base):
    __tablename__ = "rule_sets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    requirements: Mapped[list] = mapped_column(JSONB, default=list)
    source_ids: Mapped[list] = mapped_column(JSONB, default=list)
    source_versions: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("case_id", "version"),)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    fence: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    skill_hash: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    idempotency_key: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key"),)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RunEvent(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(50))
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ToolCall(Base):
    __tablename__ = "tool_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    operation_key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(80))
    arguments: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("run_id", "operation_key"),)


class Attestation(Base):
    __tablename__ = "attestations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    requirement_id: Mapped[str] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(80))
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    subject_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    legacy_logical_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(250))
    category: Mapped[str] = mapped_column(String(100), default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_asset_workspace"),
        UniqueConstraint("workspace_id", "legacy_logical_id", name="uq_asset_legacy"),
        ForeignKeyConstraint(
            ["subject_id", "workspace_id"],
            ["subject_profiles.id", "subject_profiles.workspace_id"],
            name="fk_asset_subject_workspace",
        ),
    )


class Blob(Base):
    __tablename__ = "blobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inline_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size: Mapped[int] = mapped_column(Integer)
    mime: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_blob_workspace"),
        UniqueConstraint("workspace_id", "storage_key", name="uq_blob_storage"),
        CheckConstraint("size >= 0", name="ck_blob_size"),
        CheckConstraint("storage_key IS NULL OR inline_content IS NULL", name="ck_blob_storage_kind"),
    )


class AssetRevision(Base):
    __tablename__ = "asset_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    asset_id: Mapped[str] = mapped_column(String(36), index=True)
    blob_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(250))
    origin: Mapped[str] = mapped_column(String(30), default="upload")
    text_snapshot: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("asset_id", "version", name="uq_asset_version"),
        UniqueConstraint("id", "workspace_id", name="uq_revision_workspace"),
        ForeignKeyConstraint(
            ["asset_id", "workspace_id"],
            ["assets.id", "assets.workspace_id"],
            ondelete="CASCADE",
            name="fk_revision_asset_workspace",
        ),
        ForeignKeyConstraint(
            ["blob_id", "workspace_id"], ["blobs.id", "blobs.workspace_id"], name="fk_revision_blob_workspace"
        ),
        CheckConstraint("version > 0", name="ck_asset_version"),
    )


class CaseDocumentLink(Base):
    __tablename__ = "case_document_links"
    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36))
    asset_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "case_id"],
            ["document_versions.id", "document_versions.case_id"],
            ondelete="CASCADE",
            name="fk_link_document_case",
        ),
        ForeignKeyConstraint(
            ["document_id", "asset_revision_id"],
            ["document_versions.id", "document_versions.asset_revision_id"],
            ondelete="CASCADE",
            name="fk_link_document_revision",
        ),
        ForeignKeyConstraint(
            ["case_id", "workspace_id"],
            ["cases.id", "cases.workspace_id"],
            ondelete="CASCADE",
            name="fk_link_case_workspace",
        ),
        ForeignKeyConstraint(
            ["asset_revision_id", "workspace_id"],
            ["asset_revisions.id", "asset_revisions.workspace_id"],
            name="fk_link_revision_workspace",
        ),
    )


class Issue(Base):
    __tablename__ = "issues"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[str] = mapped_column(String(100))
    rule_fingerprint: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    required: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(30), default="open")
    verdict: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    next_action: Mapped[str] = mapped_column(Text, default="")
    run_id: Mapped[str] = mapped_column(String(36))
    checked_revision: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("case_id", "requirement_id", name="uq_case_issue"),
        CheckConstraint(
            "status IN ('open','requested','submitted','resolved','exception','retired')",
            name="ck_issue_status",
        ),
    )


class IssueEvent(Base):
    __tablename__ = "issue_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    note: Mapped[str] = mapped_column(Text, default="")
    case_revision: Mapped[int] = mapped_column(Integer)
    run_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ParseRevision(Base):
    __tablename__ = "parse_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    method: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30))
    pages: Mapped[list] = mapped_column(JSONB, default=list)
    fields: Mapped[list] = mapped_column(JSONB, default=list)
    note: Mapped[str] = mapped_column(Text, default="")
    engine: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("document_id", "version", name="uq_parse_version"),)


class MaterialPacket(Base):
    __tablename__ = "material_packets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    case_revision: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict] = mapped_column(JSONB)
    input_snapshot: Mapped[dict] = mapped_column(JSONB)
    archive: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64))
    request_key: Mapped[str] = mapped_column(String(100))
    request_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("case_id", "request_key", name="uq_packet_request"),)


class DeliveryRecord(Base):
    __tablename__ = "delivery_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    packet_id: Mapped[str] = mapped_column(ForeignKey("material_packets.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    channel: Mapped[str] = mapped_column(String(200))
    recipient: Mapped[str] = mapped_column(String(200))
    reference: Mapped[str] = mapped_column(String(500), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint("status IN ('submitted','received','returned')", name="ck_delivery_status"),
    )
