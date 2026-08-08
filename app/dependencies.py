from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt
from fastapi.security import HTTPBearer
from app.db import SessionLocal
from app.models import User
from app.auth import SECRET_KEY, ALGORITHM

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token=Depends(security), db: Session = Depends(get_db)):
    payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401)
    return user

def role_required(role: str):
    def checker(user=Depends(get_current_user)):
        if user.role != role:
            raise HTTPException(status_code=403)
        return user
    return checker
