"""Create only the configured application database; never change existing roles or databases."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import psycopg
from app.config import settings
from psycopg import sql
from sqlalchemy.engine import make_url

url = make_url(settings.database_url)
if not url.database or url.database in ("postgres", "template0", "template1"):
    raise SystemExit("DATABASE_URL 必须指向独立的项目数据库")
with psycopg.connect(
    host=url.host,
    port=url.port or 5432,
    user=url.username,
    password=url.password,
    dbname="postgres",
    autocommit=True,
) as connection:
    if not connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (url.database,)).fetchone():
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))
        print("Application database created")
    else:
        print("Application database already exists")
