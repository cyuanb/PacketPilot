"""Initial schema, frozen at 0.1.0."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "\nCREATE TABLE users (\n\tid VARCHAR(36) NOT NULL, \n\tusername VARCHAR(80) NOT NULL, \n\tpassword_hash TEXT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (username)\n)\n\n"
    )
    op.execute(
        "\nCREATE TABLE auth_sessions (\n\ttoken_hash VARCHAR(64) NOT NULL, \n\tuser_id VARCHAR(36) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (token_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute(
        "\nCREATE TABLE cases (\n\tid VARCHAR(36) NOT NULL, \n\towner_id VARCHAR(36) NOT NULL, \n\ttitle VARCHAR(200) NOT NULL, \n\tinstitution VARCHAR(200) NOT NULL, \n\tkind VARCHAR(50) NOT NULL, \n\tdeadline VARCHAR(30) NOT NULL, \n\ttimezone VARCHAR(60) NOT NULL, \n\tarchived BOOLEAN NOT NULL, \n\trevision INTEGER NOT NULL, \n\tactive_rules_id VARCHAR(36), \n\tcurrent_check_id VARCHAR(36), \n\tfacts JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(owner_id) REFERENCES users (id)\n)\n\n"
    )
    op.execute(
        "\nCREATE TABLE attestations (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\trequirement_id VARCHAR(100) NOT NULL, \n\trevision INTEGER NOT NULL, \n\tnote TEXT NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute(
        "\nCREATE TABLE audit_events (\n\tid SERIAL NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\taction VARCHAR(80) NOT NULL, \n\tdata JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute(
        "\nCREATE TABLE document_versions (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tlogical_id VARCHAR(36) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\ttitle VARCHAR(250) NOT NULL, \n\tpurpose VARCHAR(20) NOT NULL, \n\tcategory VARCHAR(100) NOT NULL, \n\tfilename VARCHAR(250) NOT NULL, \n\tstorage_key VARCHAR(100) NOT NULL, \n\tsha256 VARCHAR(64) NOT NULL, \n\tmime VARCHAR(100) NOT NULL, \n\tsize INTEGER NOT NULL, \n\tparse_status VARCHAR(30) NOT NULL, \n\tpages JSONB NOT NULL, \n\tparse_note TEXT NOT NULL, \n\tparse_method VARCHAR(40) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (logical_id, version), \n\tFOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_document_versions_logical_id ON document_versions (logical_id)")
    op.execute("CREATE INDEX ix_document_versions_case_id ON document_versions (case_id)")
    op.execute(
        "\nCREATE TABLE rule_sets (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\trequirements JSONB NOT NULL, \n\tsource_ids JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (case_id, version), \n\tFOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_rule_sets_case_id ON rule_sets (case_id)")
    op.execute(
        "\nCREATE TABLE runs (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tkind VARCHAR(30) NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\trevision INTEGER NOT NULL, \n\tsnapshot JSONB NOT NULL, \n\tpayload JSONB NOT NULL, \n\tresult JSONB NOT NULL, \n\tattempt INTEGER NOT NULL, \n\tfence INTEGER NOT NULL, \n\tcancel_requested BOOLEAN NOT NULL, \n\tlease_until TIMESTAMP WITH TIME ZONE, \n\terror TEXT NOT NULL, \n\tskill_hash VARCHAR(64) NOT NULL, \n\tmodel VARCHAR(100) NOT NULL, \n\tidempotency_key VARCHAR(150), \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (case_id, idempotency_key), \n\tFOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_runs_case_id ON runs (case_id)")
    op.execute("CREATE INDEX ix_runs_status ON runs (status)")
    op.execute(
        "\nCREATE TABLE messages (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\trun_id VARCHAR(36), \n\trole VARCHAR(20) NOT NULL, \n\tcontent TEXT NOT NULL, \n\tdata JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE, \n\tFOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_messages_case_id ON messages (case_id)")
    op.execute(
        "\nCREATE TABLE run_events (\n\tid SERIAL NOT NULL, \n\trun_id VARCHAR(36) NOT NULL, \n\tevent VARCHAR(50) NOT NULL, \n\tdata JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_run_events_run_id ON run_events (run_id)")
    op.execute(
        "\nCREATE TABLE tool_calls (\n\tid VARCHAR(36) NOT NULL, \n\trun_id VARCHAR(36) NOT NULL, \n\toperation_key VARCHAR(64) NOT NULL, \n\tname VARCHAR(80) NOT NULL, \n\targuments JSONB NOT NULL, \n\tresult JSONB NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (run_id, operation_key), \n\tFOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_tool_calls_run_id ON tool_calls (run_id)")


def downgrade():
    op.drop_table("tool_calls")
    op.drop_table("run_events")
    op.drop_table("messages")
    op.drop_table("runs")
    op.drop_table("rule_sets")
    op.drop_table("document_versions")
    op.drop_table("audit_events")
    op.drop_table("attestations")
    op.drop_table("cases")
    op.drop_table("auth_sessions")
    op.drop_table("users")
