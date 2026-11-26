from alembic import context
from app import models  # noqa: F401
from app.db import Base, engine


def run_migrations(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


provided_connection = context.config.attributes.get("connection")
if provided_connection is not None:
    run_migrations(provided_connection)
else:
    with engine.connect() as connection:
        run_migrations(connection)
