from datetime import datetime,timedelta,timezone
from jose import jwt,JWTError
from passlib.context import CryptContext
from fastapi import Depends,HTTPException,status
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from .config import settings
from .db import get_db
from .models import User
pwd=CryptContext(schemes=['pbkdf2_sha256'],deprecated='auto')
bearer=HTTPBearer(auto_error=True)
def hash_password(v): return pwd.hash(v)
def verify_password(v,h): return pwd.verify(v,h)
def token(user): return jwt.encode({'sub':str(user.id),'role':user.role,'exp':datetime.now(timezone.utc)+timedelta(minutes=settings.jwt_exp_minutes)},settings.jwt_secret,algorithm='HS256')
def current_user(c:HTTPAuthorizationCredentials=Depends(bearer),db=Depends(get_db)):
    try:
        payload=jwt.decode(c.credentials,settings.jwt_secret,algorithms=['HS256']); uid=int(payload['sub']); u=db.get(User,uid)
    except (JWTError,ValueError,KeyError): u=None
    if not u: raise HTTPException(status.HTTP_401_UNAUTHORIZED,'Invalid or expired token')
    return u
def require_role(*roles):
    def dep(u=Depends(current_user)):
        if u.role not in roles: raise HTTPException(403,'Insufficient permissions')
        return u
    return dep
