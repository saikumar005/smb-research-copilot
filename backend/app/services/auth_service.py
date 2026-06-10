import logging
from typing import Optional
from datetime import timedelta
from sqlalchemy.orm import Session
from app.core import security
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserRegister
from app.models.user import User

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    def register_user(db: Session, user_data: UserRegister) -> User:
        user_repo = UserRepository(db)
        existing_user = user_repo.get_by_email(user_data.email)
        if existing_user:
            raise ValueError("Email already registered")
        
        hashed_password = security.hash_password(user_data.password)
        return user_repo.create(
            email=user_data.email,
            hashed_password=hashed_password,
            name=user_data.name
        )

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(email)
        if not user:
            return None
        
        if not security.verify_password(password, user.hashed_password):
            return None
            
        return user

    @staticmethod
    def generate_password_reset_token(db: Session, email: str) -> Optional[str]:
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(email)
        if not user:
            return None
        
        # Generate token valid for 15 minutes
        token = security.create_access_token(
            subject=user.id,
            expires_delta=timedelta(minutes=15)
        )
        
        # Simulate sending email by logging the link
        reset_link = f"http://localhost:5173/reset-password?token={token}"
        logger.warning(
            f"\n--- PASSWORD RESET SIMULATION ---\n"
            f"To: {user.email}\n"
            f"Link: {reset_link}\n"
            f"---------------------------------\n"
        )
        print(f"\n--- PASSWORD RESET SIMULATION ---\nTo: {user.email}\nLink: {reset_link}\n---------------------------------\n", flush=True)
        return token

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> bool:
        user_id_str = security.decode_access_token(token)
        if not user_id_str:
            return False
            
        try:
            user_id = int(user_id_str)
        except ValueError:
            return False
            
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)
        if not user:
            return False
            
        hashed_password = security.hash_password(new_password)
        user_repo.update_password(user, hashed_password)
        return True
