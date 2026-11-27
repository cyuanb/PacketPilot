"""Pinned case materials, scenario snapshots and verifiable amendment workflow."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cases",
        sa.Column("scenario_snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.alter_column("cases", "scenario_snapshot", server_default=None)
    op.create_unique_constraint("uq_document_case", "document_versions", ["id", "case_id"])
    op.create_unique_constraint(
        "uq_document_asset_revision", "document_versions", ["id", "asset_revision_id"]
    )
    op.create_unique_constraint("uq_revision_workspace", "asset_revisions", ["id", "workspace_id"])
    op.create_table(
        "case_document_links",
        sa.Column("document_id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("asset_revision_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id", "case_id"],
            ["document_versions.id", "document_versions.case_id"],
            ondelete="CASCADE",
            name="fk_link_document_case",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "asset_revision_id"],
            ["document_versions.id", "document_versions.asset_revision_id"],
            ondelete="CASCADE",
            name="fk_link_document_revision",
        ),
        sa.ForeignKeyConstraint(
            ["case_id", "workspace_id"],
            ["cases.id", "cases.workspace_id"],
            ondelete="CASCADE",
            name="fk_link_case_workspace",
        ),
        sa.ForeignKeyConstraint(
            ["asset_revision_id", "workspace_id"],
            ["asset_revisions.id", "asset_revisions.workspace_id"],
            name="fk_link_revision_workspace",
        ),
    )
    op.create_index("ix_case_document_links_case_id", "case_document_links", ["case_id"])
    op.create_index("ix_case_document_links_asset_revision_id", "case_document_links", ["asset_revision_id"])
    op.execute(
        "INSERT INTO case_document_links (document_id,case_id,workspace_id,asset_revision_id,created_at) SELECT d.id,d.case_id,c.workspace_id,d.asset_revision_id,d.created_at FROM document_versions d JOIN cases c ON c.id=d.case_id WHERE d.asset_revision_id IS NOT NULL"
    )
    op.create_table(
        "issues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_id", sa.String(100), nullable=False),
        sa.Column("rule_fingerprint", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("verdict", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("checked_revision", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "requirement_id", name="uq_case_issue"),
        sa.CheckConstraint(
            "status IN ('open','requested','submitted','resolved','exception','retired')",
            name="ck_issue_status",
        ),
    )
    op.create_index("ix_issues_case_id", "issues", ["case_id"])
    op.create_table(
        "issue_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issue_id", sa.String(36), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("case_revision", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_issue_events_issue_id", "issue_events", ["issue_id"])


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM issues) OR EXISTS(SELECT 1 FROM cases WHERE scenario_snapshot <> '{}'::jsonb)"
        )
    ):
        raise RuntimeError("Workflow data exists; use a verified backup instead of discarding it.")
    op.drop_table("issue_events")
    op.drop_table("issues")
    op.drop_table("case_document_links")
    op.drop_constraint("uq_revision_workspace", "asset_revisions", type_="unique")
    op.drop_constraint("uq_document_asset_revision", "document_versions", type_="unique")
    op.drop_constraint("uq_document_case", "document_versions", type_="unique")
    op.drop_column("cases", "scenario_snapshot")
