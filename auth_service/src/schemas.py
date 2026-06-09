"""
Pydantic schemas for Auth Service.
IEEE Std 830-1998 SRS compliant data validation.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field, validator, EmailStr
import uuid
from shared.models import UserRole, JWTToken


class UserBase(BaseModel):
    """Base user schema."""
    phone: str = Field(..., regex=r'^\+91[6-9]\d{9}$', description="Indian mobile number with +91 prefix")
    email: Optional[EmailStr] = Field(None, description="Optional email address")
    full_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Full name")
    role: Optional[UserRole] = Field(UserRole.CITIZEN, description="User role")


class UserCreate(UserBase):
    """User creation schema."""
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="Optional password for fallback auth")
    ward_id: Optional[uuid.UUID] = Field(None, description="Assigned ward ID for staff")
    employee_id: Optional[str] = Field(None, min_length=1, max_length=50, description="Employee ID for staff")

    @validator('password')
    def validate_password(cls, v):
        if v and len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class UserUpdate(BaseModel):
    """User update schema."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    ward_id: Optional[uuid.UUID] = None
    employee_id: Optional[str] = Field(None, min_length=1, max_length=50)


class UserResponse(UserBase):
    """User response schema."""
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    ward_id: Optional[uuid.UUID]
    employee_id: Optional[str]

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """User login schema."""
    phone: str = Field(..., regex=r'^\+91[6-9]\d{9}$')
    device_info: Optional[dict] = Field(None, description="Device information")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")


class OTPRequest(BaseModel):
    """OTP request schema."""
    phone: str = Field(..., regex=r'^\+91[6-9]\d{9}$')
    ip_address: Optional[str] = Field(None, description="Client IP address")

    @validator('phone')
    def validate_phone(cls, v):
        if not v.startswith('+91'):
            raise ValueError('Phone number must start with +91')
        if len(v) != 13:
            raise ValueError('Invalid Indian phone number format')
        return v


class OTPVerify(BaseModel):
    """OTP verification schema."""
    phone: str = Field(..., regex=r'^\+91[6-9]\d{9}$')
    otp: str = Field(..., regex=r'^\d{6}$', description="6-digit OTP")
    device_info: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    @validator('otp')
    def validate_otp(cls, v):
        if len(v) != 6:
            raise ValueError('OTP must be exactly 6 digits')
        return v


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    refresh_token: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str


class PasswordReset(BaseModel):
    """Password reset request schema."""
    phone: str = Field(..., regex=r'^\+91[6-9]\d{9}$')
    new_password: str = Field(..., min_length=8, max_length=128)
    otp: str = Field(..., regex=r'^\d{6}$')


class PasswordChange(BaseModel):
    """Password change schema."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class UserSessionResponse(BaseModel):
    """User session response schema."""
    id: uuid.UUID
    device_info: Optional[dict]
    ip_address: Optional[str]
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    is_active: bool

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Audit log response schema."""
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    action: str
    resource: Optional[str]
    outcome: str
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RolePermissionCreate(BaseModel):
    """Role permission creation schema."""
    role: UserRole
    resource: str = Field(..., min_length=1, max_length=100)
    action: str = Field(..., min_length=1, max_length=50)
    conditions: Optional[dict] = None


class RolePermissionResponse(BaseModel):
    """Role permission response schema."""
    id: uuid.UUID
    role: UserRole
    resource: str
    action: str
    conditions: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class APIResponse(BaseModel):
    """Standard API response schema."""
    success: bool
    message: str
    data: Optional[dict] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel):
    """Paginated response schema."""
    items: List[dict]
    total: int
    page: int
    per_page: int
    pages: int


class HealthCheck(BaseModel):
    """Health check response schema."""
    status: str
    timestamp: datetime
    version: str
    database: str
    redis: str


class MetricsResponse(BaseModel):
    """Metrics response schema."""
    total_users: int
    active_users: int
    daily_logins: int
    failed_attempts: int
    otp_sent_today: int
    active_sessions: int
