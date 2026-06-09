"""
Business logic services for Auth Service.
IEEE Std 830-1998 SRS compliant service layer.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException, status
import logging

from shared.utils import (
    generate_otp, cache_otp, verify_cached_otp, 
    create_jwt_token, verify_jwt_token, settings,
    mask_phone_number, send_fcm_notification
)
from .models import User, UserSession, AuditLog, OTPLog, RolePermission
from .schemas import UserCreate, UserUpdate, OTPRequest, OTPVerify

logger = logging.getLogger(__name__)


class UserService:
    """User management service."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone number."""
        return self.db.query(User).filter(User.phone == phone).first()
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def create_user(self, user_data: UserCreate) -> User:
        """Create new user."""
        # Check if user already exists
        existing_user = self.get_user_by_phone(user_data.phone)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this phone number already exists"
            )
        
        # Create new user
        db_user = User(
            phone=user_data.phone,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role,
            ward_id=user_data.ward_id,
            employee_id=user_data.employee_id
        )
        
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        
        # Log user creation
        self._log_audit(
            user_id=str(db_user.id),
            action="user_created",
            resource="users",
            outcome="success",
            details={"phone": mask_phone_number(user_data.phone)}
        )
        
        return db_user
    
    def update_user(self, user_id: str, user_data: UserUpdate) -> User:
        """Update user information."""
        user = self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update fields
        update_data = user_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        
        # Log user update
        self._log_audit(
            user_id=user_id,
            action="user_updated",
            resource="users",
            outcome="success",
            details={"updated_fields": list(update_data.keys())}
        )
        
        return user
    
    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user account."""
        user = self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = False
        self.db.commit()
        
        # Revoke all active sessions
        self.db.query(UserSession).filter(
            and_(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        ).update({"revoked_at": datetime.utcnow()})
        self.db.commit()
        
        # Log user deactivation
        self._log_audit(
            user_id=user_id,
            action="user_deactivated",
            resource="users",
            outcome="success"
        )
        
        return True
    
    def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        user = self.get_user_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            self.db.commit()
    
    def increment_failed_attempts(self, user_id: str) -> None:
        """Increment failed login attempts and lock account if needed."""
        user = self.get_user_by_id(user_id)
        if not user:
            return
        
        current_attempts = int(user.failed_login_attempts)
        current_attempts += 1
        user.failed_login_attempts = str(current_attempts)
        
        # Lock account after 5 failed attempts for 30 minutes
        if current_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        self.db.commit()
    
    def reset_failed_attempts(self, user_id: str) -> None:
        """Reset failed login attempts."""
        user = self.get_user_by_id(user_id)
        if user:
            user.failed_login_attempts = "0"
            user.locked_until = None
            self.db.commit()
    
    def _log_audit(self, user_id: Optional[str], action: str, resource: str, 
                   outcome: str, details: Optional[Dict[str, Any]] = None,
                   ip_address: Optional[str] = None) -> None:
        """Log audit event."""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            outcome=outcome,
            ip_address=ip_address,
            details=str(details) if details else None
        )
        self.db.add(audit_log)
        self.db.commit()


class OTPService:
    """OTP generation and verification service."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def send_otp(self, otp_request: OTPRequest, ip_address: Optional[str] = None) -> bool:
        """Send OTP to user's phone number."""
        phone = otp_request.phone
        
        # Check rate limiting
        recent_otp_count = self.db.query(OTPLog).filter(
            and_(
                OTPLog.phone == phone,
                OTPLog.created_at >= datetime.utcnow() - timedelta(minutes=5)
            )
        ).count()
        
        if recent_otp_count >= 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests. Please try again after 5 minutes."
            )
        
        # Generate OTP
        otp = generate_otp()
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        
        # Store OTP in database
        otp_log = OTPLog(
            phone=phone,
            otp_hash=otp_hash,
            gateway="msg91",  # or "twilio" based on configuration
            expires_at=expires_at,
            ip_address=ip_address
        )
        self.db.add(otp_log)
        self.db.commit()
        
        # Cache OTP for fast verification
        cache_otp(phone, otp)
        
        # Send SMS (implement actual SMS sending logic)
        try:
            success = self._send_sms(phone, otp)
            if success:
                otp_log.status = "sent"
            else:
                otp_log.status = "failed"
            self.db.commit()
            return success
        except Exception as e:
            logger.error(f"Failed to send OTP to {phone}: {e}")
            otp_log.status = "failed"
            self.db.commit()
            return False
    
    def verify_otp(self, otp_verify: OTPVerify, ip_address: Optional[str] = None) -> bool:
        """Verify OTP and mark as used."""
        phone = otp_verify.phone
        otp = otp_verify.otp
        
        # Get latest OTP for this phone
        otp_log = self.db.query(OTPLog).filter(
            and_(
                OTPLog.phone == phone,
                OTPLog.is_verified.is_(False),
                OTPLog.is_expired.is_(False)
            )
        ).order_by(OTPLog.created_at.desc()).first()
        
        if not otp_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No valid OTP found for this phone number"
            )
        
        # Check expiry
        if otp_log.is_expired:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired"
            )
        
        # Verify OTP hash
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        if otp_hash != otp_log.otp_hash:
            # Increment attempts
            attempts = int(otp_log.attempts) + 1
            otp_log.attempts = str(attempts)
            self.db.commit()
            
            if attempts >= 3:
                otp_log.status = "max_attempts"
                self.db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum OTP verification attempts exceeded"
                )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP"
            )
        
        # Mark OTP as verified
        otp_log.verified_at = datetime.utcnow()
        otp_log.status = "verified"
        self.db.commit()
        
        return True
    
    def _send_sms(self, phone: str, otp: str) -> bool:
        """Send SMS via configured gateway."""
        try:
            # Implementation depends on chosen gateway
            # MSG91 example:
            if hasattr(settings, 'MSG91_AUTH_KEY'):
                return self._send_via_msg91(phone, otp)
            # Twilio example:
            elif hasattr(settings, 'TWILIO_ACCOUNT_SID'):
                return self._send_via_twilio(phone, otp)
            else:
                # For development, just log the OTP
                logger.info(f"Development OTP for {phone}: {otp}")
                return True
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            return False
    
    def _send_via_msg91(self, phone: str, otp: str) -> bool:
        """Send SMS via MSG91."""
        try:
            from msg91 import sms
            response = sms.send(
                authkey=settings.MSG91_AUTH_KEY,
                mobiles=[phone.replace('+91', '')],
                message=f"Your SwachhGram OTP is: {otp}. Valid for {settings.OTP_EXPIRY_MINUTES} minutes.",
                sender="SWCHGR",
                route=4
            )
            return response.get('type') == 'success'
        except ImportError:
            logger.warning("MSG91 not available")
            return False
        except Exception as e:
            logger.error(f"MSG91 error: {e}")
            return False
    
    def _send_via_twilio(self, phone: str, otp: str) -> bool:
        """Send SMS via Twilio."""
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            message = client.messages.create(
                body=f"Your SwachhGram OTP is: {otp}. Valid for {settings.OTP_EXPIRY_MINUTES} minutes.",
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone
            )
            return message.sid is not None
        except ImportError:
            logger.warning("Twilio not available")
            return False
        except Exception as e:
            logger.error(f"Twilio error: {e}")
            return False


class SessionService:
    """User session management service."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_session(self, user_id: str, token_jti: str, 
                      device_info: Optional[Dict[str, Any]] = None,
                      ip_address: Optional[str] = None,
                      user_agent: Optional[str] = None) -> UserSession:
        """Create new user session."""
        expires_at = datetime.utcnow() + timedelta(days=7)  # 7 days expiry
        
        session = UserSession(
            user_id=user_id,
            token_jti=token_jti,
            device_info=str(device_info) if device_info else None,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def revoke_session(self, session_id: str) -> bool:
        """Revoke user session."""
        session = self.db.query(UserSession).filter(UserSession.id == session_id).first()
        if session:
            session.revoked_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
    
    def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revoke all sessions for a user."""
        count = self.db.query(UserSession).filter(
            and_(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        ).update({"revoked_at": datetime.utcnow()})
        self.db.commit()
        return count
    
    def get_active_sessions(self, user_id: str) -> List[UserSession]:
        """Get all active sessions for a user."""
        return self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > datetime.utcnow()
            )
        ).all()
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        count = self.db.query(UserSession).filter(
            or_(
                UserSession.expires_at <= datetime.utcnow(),
                UserSession.revoked_at.isnot(None)
            )
        ).delete()
        self.db.commit()
        return count


class AuthService:
    """Main authentication service."""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)
        self.otp_service = OTPService(db)
        self.session_service = SessionService(db)
    
    def authenticate_with_otp(self, otp_verify: OTPVerify,
                            device_info: Optional[Dict[str, Any]] = None,
                            ip_address: Optional[str] = None,
                            user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Authenticate user with OTP and return JWT token."""
        phone = otp_verify.phone
        
        # Verify OTP
        if not self.otp_service.verify_otp(otp_verify, ip_address):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OTP"
            )
        
        # Get or create user
        user = self.user_service.get_user_by_phone(phone)
        if not user:
            # Auto-create user for citizens
            user_data = UserCreate(
                phone=phone,
                role="citizen"
            )
            user = self.user_service.create_user(user_data)
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        # Check if account is locked
        if user.is_locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked"
            )
        
        # Reset failed attempts
        self.user_service.reset_failed_attempts(str(user.id))
        
        # Update last login
        self.user_service.update_last_login(str(user.id))
        
        # Create JWT token
        token_data = {
            "sub": str(user.id),
            "role": user.role.value,
            "phone": mask_phone_number(phone)
        }
        access_token = create_jwt_token(token_data)
        token_jti = verify_jwt_token(access_token).get("jti", "")
        
        # Create session
        self.session_service.create_session(
            user_id=str(user.id),
            token_jti=token_jti,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Log successful authentication
        self.user_service._log_audit(
            user_id=str(user.id),
            action="login_success",
            resource="auth",
            outcome="success",
            ip_address=ip_address
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
            "user": user
        }
    
    def logout(self, token_jti: str) -> bool:
        """Logout user by revoking session."""
        session = self.db.query(UserSession).filter(UserSession.token_jti == token_jti).first()
        if session:
            session.revoked_at = datetime.utcnow()
            self.db.commit()
            
            # Log logout
            self.user_service._log_audit(
                user_id=str(session.user_id),
                action="logout",
                resource="auth",
                outcome="success"
            )
            return True
        return False
