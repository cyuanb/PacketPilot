"""Persistent work and scoped collaboration."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.execute(
        "\nCREATE TABLE work_items (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tkind VARCHAR(30) NOT NULL, \n\ttitle VARCHAR(200) NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\tdetail JSONB NOT NULL, \n\trevision INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_work_items_case_id ON work_items (case_id)")
    op.execute(
        "\nCREATE TABLE work_events (\n\tid VARCHAR(36) NOT NULL, \n\titem_id VARCHAR(36) NOT NULL, \n\tactor_id VARCHAR(36) NOT NULL, \n\tdata JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(item_id) REFERENCES work_items (id) ON DELETE CASCADE, \n\tFOREIGN KEY(actor_id) REFERENCES users (id)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_work_events_item_id ON work_events (item_id)")
    op.execute(
        "\nCREATE TABLE access_grants (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tuser_id VARCHAR(36), \n\trole VARCHAR(30) NOT NULL, \n\tdocument_ids JSONB NOT NULL, \n\ttoken_hash VARCHAR(64) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\trevoked BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE, \n\tFOREIGN KEY(user_id) REFERENCES users (id), \n\tUNIQUE (token_hash)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_access_grants_case_id ON access_grants (case_id)")
    op.execute(
        "\nCREATE TABLE collection_submissions (\n\tid VARCHAR(36) NOT NULL, \n\tgrant_id VARCHAR(36) NOT NULL, \n\tfilename VARCHAR(250) NOT NULL, \n\tcontent BYTEA NOT NULL, \n\tsha256 VARCHAR(64) NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\tnote TEXT NOT NULL, \n\tdocument_id VARCHAR(36), \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(grant_id) REFERENCES access_grants (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_collection_submissions_grant_id ON collection_submissions (grant_id)")
    op.execute(
        "\nCREATE TABLE review_comments (\n\tid VARCHAR(36) NOT NULL, \n\tgrant_id VARCHAR(36) NOT NULL, \n\tdocument_id VARCHAR(36) NOT NULL, \n\tparse_revision_id VARCHAR(36), \n\tpage INTEGER NOT NULL, \n\tquote TEXT NOT NULL, \n\tcontent TEXT NOT NULL, \n\tdecision VARCHAR(20) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(grant_id) REFERENCES access_grants (id) ON DELETE CASCADE, \n\tFOREIGN KEY(document_id) REFERENCES document_versions (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_review_comments_grant_id ON review_comments (grant_id)")
    op.execute(
        "\nCREATE TABLE recovery_codes (\n\tuser_id VARCHAR(36) NOT NULL, \n\ttoken_hash VARCHAR(64) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (user_id), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n"
    )


def downgrade():
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT count(*) FROM recovery_codes")):
        raise RuntimeError("Community data exists; restore a paired backup instead")
    if conn.scalar(sa.text("SELECT count(*) FROM review_comments")):
        raise RuntimeError("Community data exists; restore a paired backup instead")
    if conn.scalar(sa.text("SELECT count(*) FROM collection_submissions")):
        raise RuntimeError("Community data exists; restore a paired backup instead")
    if conn.scalar(sa.text("SELECT count(*) FROM access_grants")):
        raise RuntimeError("Community data exists; restore a paired backup instead")
    if conn.scalar(sa.text("SELECT count(*) FROM work_events")):
        raise RuntimeError("Community data exists; restore a paired backup instead")
    if conn.scalar(sa.text("SELECT count(*) FROM work_items")):
        raise RuntimeError("Community data exists; restore a paired backup instead")
    op.drop_table("recovery_codes")
    op.drop_table("review_comments")
    op.drop_table("collection_submissions")
    op.drop_table("access_grants")
    op.drop_table("work_events")
    op.drop_table("work_items")
