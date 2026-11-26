"""Workspace ownership and distinct person/organization profiles."""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "owner_id", name="uq_workspace_owner"),
    )
    op.create_table(
        "memberships",
        sa.Column(
            "workspace_id",
            sa.String(36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.CheckConstraint("role = 'owner'", name="ck_membership_owner_only"),
    )
    op.add_column("cases", sa.Column("workspace_id", sa.String(36), nullable=True))
    connection = op.get_bind()
    for user_id in connection.execute(sa.text("SELECT id FROM users")).scalars().all():
        workspace_id = str(uuid.uuid4())
        connection.execute(
            sa.text(
                "INSERT INTO workspaces (id, owner_id, name, revision, created_at, updated_at) VALUES (:w, :u, :name, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"w": workspace_id, "u": user_id, "name": "个人工作空间"},
        )
        connection.execute(
            sa.text("INSERT INTO memberships (workspace_id, user_id, role) VALUES (:w, :u, 'owner')"),
            {"w": workspace_id, "u": user_id},
        )
        connection.execute(
            sa.text("UPDATE cases SET workspace_id = :w WHERE owner_id = :u"),
            {"w": workspace_id, "u": user_id},
        )
    op.alter_column("cases", "workspace_id", nullable=False)
    op.create_index("ix_cases_workspace_id", "cases", ["workspace_id"])
    op.create_unique_constraint("uq_cases_workspace", "cases", ["id", "workspace_id"])
    op.create_foreign_key(
        "fk_cases_workspace_owner", "cases", "workspaces", ["workspace_id", "owner_id"], ["id", "owner_id"]
    )
    op.create_table(
        "subject_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("attributes", JSONB(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_subject_workspace"),
        sa.CheckConstraint("kind IN ('person', 'organization')", name="ck_subject_kind"),
    )
    op.create_index("ix_subject_profiles_workspace_id", "subject_profiles", ["workspace_id"])
    op.create_table(
        "case_subject_roles",
        sa.Column("case_id", sa.String(36), primary_key=True),
        sa.Column("subject_id", sa.String(36), primary_key=True),
        sa.Column("role", sa.String(30), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id", "workspace_id"],
            ["cases.id", "cases.workspace_id"],
            ondelete="CASCADE",
            name="fk_role_case_workspace",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id", "workspace_id"],
            ["subject_profiles.id", "subject_profiles.workspace_id"],
            name="fk_role_subject_workspace",
        ),
        sa.CheckConstraint(
            "role IN ('applicant', 'recommender', 'representative', 'organization', 'contact', 'other')",
            name="ck_subject_role",
        ),
    )
    op.create_index("ix_case_subject_roles_workspace_id", "case_subject_roles", ["workspace_id"])


def downgrade():
    # Refuse to silently discard profiles or edited workspace names.
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM subject_profiles) OR EXISTS(SELECT 1 FROM workspaces WHERE revision > 1)"
        )
    ):
        raise RuntimeError("Workspace data exists; export it before choosing a rollback strategy.")
    op.drop_table("case_subject_roles")
    op.drop_table("subject_profiles")
    op.drop_constraint("fk_cases_workspace_owner", "cases", type_="foreignkey")
    op.drop_constraint("uq_cases_workspace", "cases", type_="unique")
    op.drop_index("ix_cases_workspace_id", table_name="cases")
    op.drop_column("cases", "workspace_id")
    op.drop_table("memberships")
    op.drop_table("workspaces")
