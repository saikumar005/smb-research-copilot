import secrets
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User
from app.core.security import hash_password


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email.lower()).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_google_id(self, google_id: str) -> Optional[User]:
        """Look up a user by their Google subject ID (stable across name/email changes)."""
        return self.db.query(User).filter(User.google_id == google_id).first()

    def create(self, email: str, hashed_password: str, name: Optional[str] = None) -> User:
        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            name=name
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_google_user(self, email: str, name: Optional[str], google_id: str) -> User:
        """
        Create a new user that authenticated via Google SSO.
        A random unguessable password is set so the row is valid but the account
        cannot be accessed via email/password login without an explicit reset.
        """
        random_password = secrets.token_hex(32)
        user = User(
            email=email.lower(),
            hashed_password=hash_password(random_password),
            name=name,
            google_id=google_id,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def link_google_id(self, user: User, google_id: str) -> User:
        """
        Link a Google account to an existing email/password user.
        Called when a user signs in with Google using an email that already
        has a local account — merges the identities.
        """
        user.google_id = google_id
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_password(self, user: User, hashed_password: str) -> User:
        user.hashed_password = hashed_password
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
