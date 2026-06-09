"""
FastAPI application for Auth Service.
IEEE Std 830-1998 SRS compliant REST API.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import uuid

from shared.middleware import get_standard_middleware, get_current_user, require_role
from shared.utils import verify_jwt_token, settings
from .database import get_db, create_tables
from .models import User, UserSession, AuditLog
from .schemas import (
    UserResponse, UserCreate, UserUpdate, OTPRequest, OTPVerify, 
    TokenResponse, UserSessionResponse, AuditLogResponse,
    APIResponse, PaginatedResponse, HealthCheck, MetricsResponse
)
from .services import AuthService, UserService, OTPService, SessionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SwachhGram Auth Service",
    description="Authentication and Authorization Service for SwachhGram Waste Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Apply standard middleware
app = get_standard_middleware(app, allowed_origins=["http://localhost:3000"])

# Security
security = HTTPBearer()

# Dependency injection
def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Get auth service instance."""
    return AuthService(db)

def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Get user service instance."""
    return UserService(db)

def get_otp_service(db: Session = Depends(get_db)) -> OTPService:
    """Get OTP service instance."""
    return OTPService(db)

def get_session_service(db: Session = Depends(get_db)) -> SessionService:
    """Get session service instance."""
    return SessionService(db)


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup."""
    try:
        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")


# Health check endpoints
@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        database="connected",  # TODO: Add actual DB health check
        redis="connected"     # TODO: Add actual Redis health check
    )


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin"]))
):
    """Get system metrics (admin only)."""
    user_service = UserService(db)
    session_service = SessionService(db)
    
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    daily_logins = db.query(AuditLog).filter(
        AuditLog.action == "login_success",
        AuditLog.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()
    failed_attempts = db.query(AuditLog).filter(
        AuditLog.action == "login_failed",
        AuditLog.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()
    active_sessions = db.query(UserSession).filter(
        UserSession.revoked_at.is_(None),
        UserSession.expires_at > datetime.utcnow()
    ).count()
    
    return MetricsResponse(
        total_users=total_users,
        active_users=active_users,
        daily_logins=daily_logins,
        failed_attempts=failed_attempts,
        otp_sent_today=0,  # TODO: Implement OTP metrics
        active_sessions=active_sessions
    )


# Authentication endpoints
@app.post("/auth/otp/request", response_model=APIResponse)
async def request_otp(
    otp_request: OTPRequest,
    request: Request,
    otp_service: OTPService = Depends(get_otp_service)
):
    """Request OTP for phone number."""
    try:
        ip_address = request.client.host
        success = otp_service.send_otp(otp_request, ip_address)
        
        if success:
            return APIResponse(
                success=True,
                message="OTP sent successfully"
            )
        else:
            return APIResponse(
                success=False,
                message="Failed to send OTP",
                error_code="SMS_SEND_FAILED"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OTP request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.post("/auth/otp/verify", response_model=TokenResponse)
async def verify_otp(
    otp_verify: OTPVerify,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Verify OTP and authenticate user."""
    try:
        ip_address = request.client.host
        user_agent = request.headers.get("user-agent")
        device_info = {
            "ip": ip_address,
            "user_agent": user_agent
        }
        
        result = auth_service.authenticate_with_otp(
            otp_verify=otp_verify,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return TokenResponse(
            access_token=result["access_token"],
            token_type=result["token_type"],
            expires_in=result["expires_in"],
            user=UserResponse.from_orm(result["user"])
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OTP verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@app.post("/auth/logout", response_model=APIResponse)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Logout user and revoke session."""
    try:
        token = credentials.credentials
        payload = verify_jwt_token(token)
        token_jti = payload.get("jti", "")
        
        success = auth_service.logout(token_jti)
        
        if success:
            return APIResponse(
                success=True,
                message="Logged out successfully"
            )
        else:
            return APIResponse(
                success=False,
                message="Session not found",
                error_code="SESSION_NOT_FOUND"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


# User management endpoints
@app.get("/users/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Get current user information."""
    try:
        user = user_service.get_user_by_id(current_user["user_id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return UserResponse.from_orm(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user info failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )


@app.put("/users/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Update current user information."""
    try:
        user = user_service.update_user(current_user["user_id"], user_update)
        return UserResponse.from_orm(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@app.get("/users", response_model=PaginatedResponse)
async def list_users(
    page: int = 1,
    per_page: int = 20,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "ward_supervisor", "zonal_commissioner"]))
):
    """List users with pagination and filtering."""
    try:
        query = db.query(User)
        
        if role:
            query = query.filter(User.role == role)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        total = query.count()
        offset = (page - 1) * per_page
        users = query.offset(offset).limit(per_page).all()
        
        return PaginatedResponse(
            items=[UserResponse.from_orm(user) for user in users],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page
        )
    except Exception as e:
        logger.error(f"List users failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@app.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin"]))
):
    """Create new user (admin only)."""
    try:
        user = user_service.create_user(user_data)
        return UserResponse.from_orm(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create user failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    user_service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin"]))
):
    """Update user (admin only)."""
    try:
        user = user_service.update_user(user_id, user_update)
        return UserResponse.from_orm(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@app.delete("/users/{user_id}", response_model=APIResponse)
async def deactivate_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin"]))
):
    """Deactivate user (admin only)."""
    try:
        success = user_service.deactivate_user(user_id)
        if success:
            return APIResponse(
                success=True,
                message="User deactivated successfully"
            )
        else:
            return APIResponse(
                success=False,
                message="Failed to deactivate user",
                error_code="DEACTIVATION_FAILED"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deactivate user failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user"
        )


# Session management endpoints
@app.get("/sessions", response_model=List[UserSessionResponse])
async def get_user_sessions(
    current_user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service)
):
    """Get current user's active sessions."""
    try:
        sessions = session_service.get_active_sessions(current_user["user_id"])
        return [UserSessionResponse.from_orm(session) for session in sessions]
    except Exception as e:
        logger.error(f"Get sessions failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sessions"
        )


@app.delete("/sessions/{session_id}", response_model=APIResponse)
async def revoke_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user)
):
    """Revoke specific session."""
    try:
        # Verify session belongs to current user
        session = session_service.db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.user_id == current_user["user_id"]
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        success = session_service.revoke_session(session_id)
        if success:
            return APIResponse(
                success=True,
                message="Session revoked successfully"
            )
        else:
            return APIResponse(
                success=False,
                message="Failed to revoke session",
                error_code="REVOKE_FAILED"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke session failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session"
        )


# Audit log endpoints
@app.get("/audit/logs", response_model=PaginatedResponse)
async def get_audit_logs(
    page: int = 1,
    per_page: int = 20,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin"]))
):
    """Get audit logs (admin only)."""
    try:
        query = db.query(AuditLog)
        
        if action:
            query = query.filter(AuditLog.action == action)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        query = query.order_by(AuditLog.created_at.desc())
        
        total = query.count()
        offset = (page - 1) * per_page
        logs = query.offset(offset).limit(per_page).all()
        
        return PaginatedResponse(
            items=[AuditLogResponse.from_orm(log) for log in logs],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page
        )
    except Exception as e:
        logger.error(f"Get audit logs failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get audit logs"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
