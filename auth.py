from enum import Enum
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

class UserRole(str, Enum):
    ADMIN = "admin"
    PRODUCER = "producer"
    RETAILER = "retailer"
    TRANSPORTER = "transporter"
    CONSUMER = "consumer"

class User(BaseModel):
    id: str
    username: str
    role: UserRole
    wallet_address: Optional[str] = None  # Only for admin

class AuthService:
    def __init__(self):
        # Demo users - in production, use proper authentication
        self.demo_users = {
            "admin": User(id="1", username="admin", role=UserRole.ADMIN, wallet_address=None),
            "producer": User(id="2", username="producer", role=UserRole.PRODUCER),
            "retailer": User(id="3", username="retailer", role=UserRole.RETAILER),
            "transporter": User(id="4", username="transporter", role=UserRole.TRANSPORTER),
            "consumer": User(id="5", username="consumer", role=UserRole.CONSUMER),
        }
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username/password (demo implementation)"""
        if username in self.demo_users and password == "demo123":
            return self.demo_users[username]
        return None
    
    def get_user_by_token(self, token: str) -> Optional[User]:
        """Get user by token (demo implementation)"""
        # In production, decode JWT token
        if token in self.demo_users:
            return self.demo_users[token]
        return None

auth_service = AuthService()

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[User]:
    """Get current user from token (optional for public endpoints)"""
    if not credentials:
        return None
    
    user = auth_service.get_user_by_token(credentials.credentials)
    return user

def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Require authentication"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    user = auth_service.get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    return user

def require_role(allowed_roles: list[UserRole]):
    """Require specific role(s)"""
    def role_checker(user: User = Depends(require_auth)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[role.value for role in allowed_roles]}"
            )
        return user
    return role_checker

# Role-specific dependencies
require_admin = require_role([UserRole.ADMIN])
require_producer = require_role([UserRole.PRODUCER])
require_retailer = require_role([UserRole.RETAILER])
require_transporter = require_role([UserRole.TRANSPORTER])
require_consumer = require_role([UserRole.CONSUMER])
require_retailer_or_transporter = require_role([UserRole.RETAILER, UserRole.TRANSPORTER])
require_admin_or_retailer = require_role([UserRole.ADMIN, UserRole.RETAILER])
require_admin_or_producer = require_role([UserRole.ADMIN, UserRole.PRODUCER])
require_supply_chain_roles = require_role([
    UserRole.ADMIN,
    UserRole.PRODUCER,
    UserRole.RETAILER,
    UserRole.TRANSPORTER
])
require_producer_or_retailer = require_role([UserRole.PRODUCER, UserRole.RETAILER])