from argon2 import PasswordHasher
from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import User


def main():
    if len(settings.owner_password) < 10:
        raise SystemExit("请在本地 .env 配置不少于 10 位的 OWNER_PASSWORD")
    with SessionLocal.begin() as db:
        if not db.scalar(select(User).where(User.username == settings.owner_username)):
            db.add(
                User(
                    username=settings.owner_username,
                    password_hash=PasswordHasher().hash(settings.owner_password),
                )
            )
            print("Owner account created")
        else:
            print("Owner account already exists (password unchanged)")
    settings.storage.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    main()
