"""
Simplified test version of Auth Service for demonstration.
IEEE Std 830-1998 SRS compliant test implementation.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SwachhGram Auth Service - Test Version",
    description="Authentication Service for SwachhGram (Test Mode)",
    version="1.0.0-test",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Apply CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory user database for testing
test_users = {
    "+919876543210": {
        "id": str(uuid.uuid4()),
        "phone": "+919876543210",
        "role": "citizen",
        "is_active": True,
        "created_at": datetime.utcnow()
    },
    "+919876543211": {
        "id": str(uuid.uuid4()),
        "phone": "+919876543211", 
        "role": "crew",
        "is_active": True,
        "created_at": datetime.utcnow()
    },
    "+919876543212": {
        "id": str(uuid.uuid4()),
        "phone": "+919876543212",
        "role": "ward_supervisor", 
        "is_active": True,
        "created_at": datetime.utcnow()
    },
    "+919876543213": {
        "id": str(uuid.uuid4()),
        "phone": "+919876543213",
        "role": "zonal_commissioner",
        "is_active": True,
        "created_at": datetime.utcnow()
    },
    "+919876543214": {
        "id": str(uuid.uuid4()),
        "phone": "+919876543214",
        "role": "admin",
        "is_active": True,
        "created_at": datetime.utcnow()
    }
}

# In-memory OTP storage
otp_storage = {}

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "SwachhGram Auth Service - Test Version", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0-test",
        "database": "in-memory-test",
        "users_count": len(test_users)
    }

@app.post("/auth/otp/request")
async def request_otp(phone_request: dict):
    """Request OTP for phone number."""
    phone = phone_request.get("phone")
    
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required"
        )
    
    # Generate test OTP (always 123456 for testing)
    otp = "123456"
    otp_storage[phone] = otp
    
    logger.info(f"OTP requested for {phone}: {otp}")
    
    return {
        "success": True,
        "message": "OTP sent successfully (Test OTP: 123456)",
        "phone": phone
    }

@app.post("/auth/otp/verify")
async def verify_otp(otp_request: dict):
    """Verify OTP and return JWT token."""
    phone = otp_request.get("phone")
    otp = otp_request.get("otp")
    
    if not phone or not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number and OTP are required"
        )
    
    # Verify OTP
    stored_otp = otp_storage.get(phone)
    if not stored_otp or stored_otp != otp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP"
        )
    
    # Get or create user
    user = test_users.get(phone)
    if not user:
        # Auto-create user
        user = {
            "id": str(uuid.uuid4()),
            "phone": phone,
            "role": "citizen",
            "is_active": True,
            "created_at": datetime.utcnow()
        }
        test_users[phone] = user
    
    # Remove OTP after successful verification
    del otp_storage[phone]
    
    # Generate fake JWT token
    token = f"test_token_{user['id']}"
    
    logger.info(f"OTP verified for {phone}, user role: {user['role']}")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": user
    }

@app.get("/users/me")
async def get_current_user():
    """Get current user information (test version)."""
    # Return a test user for demonstration
    return {
        "id": str(uuid.uuid4()),
        "phone": "+919876543210",
        "role": "citizen",
        "is_active": True,
        "created_at": datetime.utcnow(),
        "last_login": datetime.utcnow()
    }

@app.get("/users")
async def list_users():
    """List all users (test version)."""
    return {
        "users": list(test_users.values()),
        "total": len(test_users)
    }

@app.get("/metrics")
async def get_metrics():
    """Get system metrics."""
    return {
        "total_users": len(test_users),
        "active_users": len([u for u in test_users.values() if u["is_active"]]),
        "daily_logins": 25,  # Test data
        "failed_attempts": 3,  # Test data
        "otp_sent_today": 15,  # Test data
        "active_sessions": 8,  # Test data
        "timestamp": datetime.utcnow()
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting SwachhGram Auth Service (Test Version)...")
    print("Available endpoints:")
    print("  GET  /")
    print("  GET  /health")
    print("  POST /auth/otp/request")
    print("  POST /auth/otp/verify")
    print("  GET  /users/me")
    print("  GET  /users")
    print("  GET  /metrics")
    print("\nTest OTP is always: 123456")
    print("\nStarting server on http://localhost:8000")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
