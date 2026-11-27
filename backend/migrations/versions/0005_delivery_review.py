"""Frozen packets, versioned parsing and explicit material assignments."""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None


def upgrade():
    op.add_column("document_versions", sa.Column("current_parse_id", sa.String(36)))
    op.add_column("document_versions", sa.Column("assignment", JSONB, nullable=False, server_default="{}"))
    op.add_column("rule_sets", sa.Column("source_versions", JSONB, nullable=False, server_default="{}"))
    op.create_table(
        "parse_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("parent_id", sa.String(36)),
        sa.Column("method", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("pages", JSONB, nullable=False),
        sa.Column("fields", JSONB, nullable=False),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("engine", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "version", name="uq_parse_version"),
    )
    op.create_index("ix_parse_revisions_document_id", "parse_revisions", ["document_id"])
    op.create_table(
        "material_packets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("case_revision", sa.Integer, nullable=False),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("input_snapshot", JSONB, nullable=False),
        sa.Column("archive", sa.LargeBinary, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "request_key", name="uq_packet_request"),
    )
    op.create_index("ix_material_packets_case_id", "material_packets", ["case_id"])
    op.create_table(
        "delivery_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "packet_id",
            sa.String(36),
            sa.ForeignKey("material_packets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(200), nullable=False),
        sa.Column("recipient", sa.String(200), nullable=False),
        sa.Column("reference", sa.String(500), nullable=False),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('submitted','received','returned')", name="ck_delivery_status"),
    )
    op.create_index("ix_delivery_records_packet_id", "delivery_records", ["packet_id"])
    conn = op.get_bind()
    # Copy current projections exactly. This does not OCR, infer fields or rewrite old evidence.
    docs = list(
        conn.execute(
            sa.text(
                "SELECT id, pages, parse_method, parse_status, parse_note, created_at FROM document_versions"
            )
        ).mappings()
    )
    table = sa.table(
        "parse_revisions",
        sa.column("id"),
        sa.column("document_id"),
        sa.column("version"),
        sa.column("method"),
        sa.column("status"),
        sa.column("pages", JSONB),
        sa.column("fields", JSONB),
        sa.column("note"),
        sa.column("engine"),
        sa.column("created_at"),
    )
    for d in docs:
        identifier = str(uuid.uuid4())
        conn.execute(
            table.insert().values(
                id=identifier,
                document_id=d["id"],
                version=1,
                method=d["parse_method"],
                status=d["parse_status"],
                pages=d["pages"],
                fields=[],
                note=d["parse_note"],
                engine="legacy",
                created_at=d["created_at"],
            )
        )
        conn.execute(
            sa.text("UPDATE document_versions SET current_parse_id=:p WHERE id=:id"),
            {"p": identifier, "id": d["id"]},
        )
    conn.execute(
        sa.text("""UPDATE rule_sets r SET source_versions = COALESCE((
        SELECT jsonb_object_agg(d.id, d.current_parse_id) FROM document_versions d
        WHERE r.source_ids ? d.id), '{}'::jsonb)""")
    )
    op.alter_column("document_versions", "assignment", server_default=None)
    op.alter_column("rule_sets", "source_versions", server_default=None)


def downgrade():
    conn = op.get_bind()
    if conn.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM material_packets) OR EXISTS(SELECT 1 FROM parse_revisions WHERE version > 1) OR EXISTS(SELECT 1 FROM document_versions WHERE assignment <> '{}'::jsonb)"
        )
    ):
        raise RuntimeError("Delivery/review data exists; restore a paired backup instead of dropping history")
    for table in ("delivery_records", "material_packets", "parse_revisions"):
        op.drop_table(table)
    op.drop_column("rule_sets", "source_versions")
    op.drop_column("document_versions", "assignment")
    op.drop_column("document_versions", "current_parse_id")
