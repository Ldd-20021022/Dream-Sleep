"""Shared dependencies — eliminates repeated imports across 5 routers."""
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services import get_current_user


def current_user_and_db(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user, db
