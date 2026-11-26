"""Independent assets, immutable revisions and original bytes; preserve legacy references."""

import hashlib
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=True),
        sa.Column("legacy_logical_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_asset_workspace"),
        sa.UniqueConstraint("workspace_id", "legacy_logical_id", name="uq_asset_legacy"),
        sa.ForeignKeyConstraint(
            ["subject_id", "workspace_id"],
            ["subject_profiles.id", "subject_profiles.workspace_id"],
            name="fk_asset_subject_workspace",
        ),
    )
    op.create_index("ix_assets_workspace_id", "assets", ["workspace_id"])
    op.create_table(
        "blobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("storage_key", sa.String(100), nullable=True),
        sa.Column("inline_content", sa.LargeBinary(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("mime", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_blob_workspace"),
        sa.UniqueConstraint("workspace_id", "storage_key", name="uq_blob_storage"),
        sa.CheckConstraint("size >= 0", name="ck_blob_size"),
        sa.CheckConstraint("storage_key IS NULL OR inline_content IS NULL", name="ck_blob_storage_kind"),
    )
    op.create_index("ix_blobs_workspace_id", "blobs", ["workspace_id"])
    op.create_index("ix_blobs_sha256", "blobs", ["sha256"])
    op.create_table(
        "asset_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("asset_id", sa.String(36), nullable=False),
        sa.Column("blob_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(250), nullable=False),
        sa.Column("origin", sa.String(30), nullable=False),
        sa.Column("text_snapshot", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("asset_id", "version", name="uq_asset_version"),
        sa.ForeignKeyConstraint(
            ["asset_id", "workspace_id"],
            ["assets.id", "assets.workspace_id"],
            ondelete="CASCADE",
            name="fk_revision_asset_workspace",
        ),
        sa.ForeignKeyConstraint(
            ["blob_id", "workspace_id"], ["blobs.id", "blobs.workspace_id"], name="fk_revision_blob_workspace"
        ),
        sa.CheckConstraint("version > 0", name="ck_asset_version"),
    )
    for column in ("workspace_id", "asset_id", "blob_id"):
        op.create_index("ix_asset_revisions_" + column, "asset_revisions", [column])
    op.add_column("document_versions", sa.Column("asset_revision_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_document_asset_revision", "document_versions", "asset_revisions", ["asset_revision_id"], ["id"]
    )
    op.create_index("ix_document_versions_asset_revision_id", "document_versions", ["asset_revision_id"])
    connection = op.get_bind()
    metadata = sa.MetaData()
    assets = sa.Table("assets", metadata, autoload_with=connection)
    blobs = sa.Table("blobs", metadata, autoload_with=connection)
    revisions = sa.Table("asset_revisions", metadata, autoload_with=connection)
    documents = sa.Table("document_versions", metadata, autoload_with=connection)
    cases = sa.Table("cases", metadata, autoload_with=connection)
    groups, originals, original_metadata = {}, {}, {}
    rows = (
        connection.execute(
            sa.select(documents, cases.c.workspace_id)
            .join(cases, cases.c.id == documents.c.case_id)
            .order_by(cases.c.workspace_id, documents.c.logical_id, documents.c.version)
        )
        .mappings()
        .all()
    )
    for doc in rows:
        group = (doc["workspace_id"], doc["logical_id"])
        if group not in groups:
            groups[group] = str(uuid.uuid4())
            connection.execute(
                assets.insert().values(
                    id=groups[group],
                    workspace_id=group[0],
                    legacy_logical_id=group[1],
                    title=doc["title"],
                    category=doc["category"],
                    archived=False,
                    revision=1,
                    created_at=doc["created_at"],
                    updated_at=doc["created_at"],
                )
            )
        asset_id = groups[group]
        # Corrections can retain an earlier original hash while holding different text.
        key = (group[0], doc["storage_key"]) if doc["storage_key"] else (*group, doc["sha256"], doc["size"])
        recorded = (doc["sha256"], doc["size"], doc["mime"])
        if key in original_metadata and original_metadata[key] != recorded:
            raise RuntimeError("Conflicting legacy metadata for a shared original; migration aborted.")
        original_metadata[key] = recorded
        if key not in originals:
            candidate = "\n\n".join(page.get("text", "") for page in doc["pages"]).encode()
            inline = (
                candidate
                if not doc["storage_key"]
                and hashlib.sha256(candidate).hexdigest() == doc["sha256"]
                and len(candidate) == doc["size"]
                else None
            )
            originals[key] = str(uuid.uuid4())
            connection.execute(
                blobs.insert().values(
                    id=originals[key],
                    workspace_id=group[0],
                    storage_key=doc["storage_key"] or None,
                    inline_content=inline,
                    sha256=doc["sha256"],
                    size=doc["size"],
                    mime=doc["mime"],
                    created_at=doc["created_at"],
                )
            )
        connection.execute(
            revisions.insert().values(
                id=doc["id"],
                workspace_id=group[0],
                asset_id=asset_id,
                blob_id=originals[key],
                version=doc["version"],
                filename=doc["filename"],
                origin="correction" if doc["parse_method"] == "user_corrected" else "legacy",
                text_snapshot=doc["pages"],
                created_at=doc["created_at"],
            )
        )
        connection.execute(
            documents.update().where(documents.c.id == doc["id"]).values(asset_revision_id=doc["id"])
        )
        connection.execute(
            assets.update()
            .where(assets.c.id == asset_id)
            .values(title=doc["title"], category=doc["category"], updated_at=doc["created_at"])
        )
    op.execute(
        """CREATE FUNCTION prevent_library_content_update() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Library originals and revisions are immutable; append a new revision'; END; $$"""
    )
    for table in ("blobs", "asset_revisions"):
        op.execute(
            f"CREATE TRIGGER immutable_{table} BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_library_content_update()"
        )


def downgrade():
    # Library uploads and detached originals cannot be represented in the earlier schema.
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM assets)")):
        raise RuntimeError(
            "Library data exists; restore a pre-migration backup instead of discarding originals."
        )
    op.drop_constraint("fk_document_asset_revision", "document_versions", type_="foreignkey")
    op.drop_index("ix_document_versions_asset_revision_id", table_name="document_versions")
    op.drop_column("document_versions", "asset_revision_id")
    op.drop_table("asset_revisions")
    op.drop_table("blobs")
    op.execute("DROP FUNCTION prevent_library_content_update()")
    op.drop_table("assets")
