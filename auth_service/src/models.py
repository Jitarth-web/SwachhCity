"""
Database models for Auth Service.
IEEE Std 830-1998 SRS compliant data models.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from datetime import datetime
import uuid
from shared.models import UserRole
from .database import Base


class User(Base):
    """
    User model for authentication and authorization.
    Stores user information with DPDP compliance.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    phone = Column(String(15), unique=True, index=True, nullable=False, comment="Indian mobile number with +91 prefix")
    email = Column(String(255), unique=True, index=True, nullable=True, comment="Optional email address")
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CITIZEN, comment="User role for RBAC")
    is_active = Column(Boolean, default=True, nullable=False, comment="Account status")
    is_verified = Column(Boolean, default=False, nullable=False, comment="Phone verification status")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Account creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")
    last_login = Column(DateTime(timezone=True), nullable=True, comment="Last successful login timestamp")
    failed_login_attempts = Column(String(3), default="0", nullable=False, comment="Failed login attempt count")
    locked_until = Column(DateTime(timezone=True), nullable=True, comment="Account lockout timestamp")
    
    # Additional profile fields
    full_name = Column(String(100), nullable=True, comment="Full name (optional)")
    ward_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="Assigned ward ID for staff")
    employee_id = Column(String(50), nullable=True, unique=True, comment="Employee ID for staff")
    
    # Security fields
    password_hash = Column(String(255), nullable=True, comment="Optional password for fallback auth")
    two_factor_enabled = Column(Boolean, default=False, nullable=False, comment="2FA status")
    device_tokens = Column(Text, nullable=True, comment="FCM device tokens (JSON array)")

    def __repr__(self):
        return f"<User(id={self.id}, phone={self.phone}, role={self.role})>"

    @property
    def is_locked(self):
        """Check if account is currently locked."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_utc

    @property
    def locked_until_utc(self):
        """Get lockout timestamp in UTC."""
        return self.locked_until.replace(tzinfo=None) if self.locked_until else None


class UserSession(Base):
    """
    User session model for JWT token management.
    Tracks active sessions for security monitoring.
    """
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="User ID reference")
    token_jti = Column(String(255), unique=True, nullable=False, index=True, comment="JWT token ID")
    device_info = Column(Text, nullable=True, comment="Device information (JSON)")
    ip_address = Column(String(45), nullable=True, comment="Client IP address")
    user_agent = Column(Text, nullable=True, comment="User agent string")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Session creation timestamp")
    expires_at = Column(DateTime(timezone=True), nullable=False, comment="Session expiry timestamp")
    revoked_at = Column(DateTime(timezone=True), nullable=True, comment="Session revocation timestamp")
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Last activity timestamp")

    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"

    @property
    def is_active(self):
        """Check if session is currently active."""
        now = datetime.utcnow()
        return (self.revoked_at is None and 
                now < self.expires_at.replace(tzinfo=None))


class AuditLog(Base):
    """
    Audit log model for security and compliance.
    Tracks all authentication and authorization events.
    """
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="User ID (null for anonymous)")
    action = Column(String(100), nullable=False, index=True, comment="Action performed")
    resource = Column(String(100), nullable=True, comment="Resource accessed")
    outcome = Column(String(20), nullable=False, index=True, comment="Action outcome (success/failure/error)")
    ip_address = Column(String(45), nullable=True, comment="Client IP address")
    user_agent = Column(Text, nullable=True, comment="User agent string")
    details = Column(Text, nullable=True, comment="Additional details (JSON)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Event timestamp")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action={self.action}, outcome={self.outcome})>"


class OTPLog(Base):
    """
    OTP log model for SMS tracking and rate limiting.
    Maintains compliance with telecom regulations.
    """
    __tablename__ = "otp_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    phone = Column(String(15), nullable=False, index=True, comment="Phone number")
    otp_hash = Column(String(255), nullable=False, comment="Hashed OTP value")
    gateway = Column(String(50), nullable=False, comment="SMS gateway used")
    gateway_message_id = Column(String(100), nullable=True, comment="Gateway message ID")
    status = Column(String(20), nullable=False, default="sent", comment="Delivery status")
    attempts = Column(String(2), default="1", nullable=False, comment="Verification attempts")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="OTP generation timestamp")
    expires_at = Column(DateTime(timezone=True), nullable=False, comment="OTP expiry timestamp")
    verified_at = Column(DateTime(timezone=True), nullable=True, comment="Verification timestamp")
    ip_address = Column(String(45), nullable=True, comment="Request IP address")

    def __repr__(self):
        return f"<OTPLog(id={self.id}, phone={self.phone}, status={self.status})>"

    @property
    def is_expired(self):
        """Check if OTP has expired."""
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)

    @property
    def is_verified(self):
        """Check if OTP has been verified."""
        return self.verified_at is not None


class RolePermission(Base):
    """
    Role permissions model for fine-grained RBAC.
    Defines what each role can access.
    """
    __tablename__ = "role_permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    role = Column(Enum(UserRole), nullable=False, index=True, comment="User role")
    resource = Column(String(100), nullable=False, index=True, comment="Resource name")
    action = Column(String(50), nullable=False, comment="Allowed action (create/read/update/delete)")
    conditions = Column(Text, nullable=True, comment="Additional conditions (JSON)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Permission creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")

    def __repr__(self):
        return f"<RolePermission(id={self.id}, role={self.role}, resource={self.resource}, action={self.action})>"
