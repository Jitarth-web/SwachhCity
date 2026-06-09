"""
Fixed version of Auth Service with username/password login.
IEEE Std 830-1998 SRS compliant test implementation.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import logging
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SwachhGram Auth Service - Fixed Version",
    description="Authentication Service for SwachhGram (Username/Password)",
    version="1.0.0-fixed",
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

# User database with username/password
users_db = {
    "admin": {
        "id": str(uuid.uuid4()),
        "username": "admin",
        "password": hashlib.sha256("admin123".encode()).hexdigest(),  # Hashed password
        "role": "admin",
        "name": "System Administrator",
        "is_active": True,
        "created_at": datetime.utcnow()
    },
    "supervisor": {
        "id": str(uuid.uuid4()),
        "username": "supervisor",
        "password": hashlib.sha256("sup123".encode()).hexdigest(),
        "role": "ward_supervisor",
        "name": "Ward Supervisor",
        "is_active": True,
        "created_at": datetime.utcnow()
    },
    "crew": {
        "id": str(uuid.uuid4()),
        "username": "crew",
        "password": hashlib.sha256("crew123".encode()).hexdigest(),
        "role": "crew",
        "name": "Collection Crew",
        "is_active": True,
        "created_at": datetime.utcnow()
    },
    "citizen": {
        "id": str(uuid.uuid4()),
        "username": "citizen",
        "password": hashlib.sha256("cit123".encode()).hexdigest(),
        "role": "citizen",
        "name": "Citizen User",
        "is_active": True,
        "created_at": datetime.utcnow()
    }
}

# Session storage
sessions = {}

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "SwachhGram Auth Service - Fixed Version", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0-fixed",
        "database": "in-memory-test",
        "users_count": len(users_db),
        "active_sessions": len(sessions)
    }

@app.post("/auth/login")
async def login(login_request: dict):
    """Login with username and password."""
    username = login_request.get("username")
    password = login_request.get("password")
    
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required"
        )
    
    # Find user
    user = users_db.get(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Check password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    if user["password"] != hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Check if user is active
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled"
        )
    
    # Create session token
    session_token = str(uuid.uuid4())
    sessions[session_token] = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "created_at": datetime.utcnow()
    }
    
    # Update last login
    user["last_login"] = datetime.utcnow()
    
    logger.info(f"User {username} logged in successfully")
    
    return {
        "access_token": session_token,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "role": user["role"],
            "is_active": user["is_active"],
            "last_login": user["last_login"]
        }
    }

@app.post("/auth/logout")
async def logout(auth_request: dict):
    """Logout user."""
    token = auth_request.get("token")
    if token and token in sessions:
        del sessions[token]
    
    return {"success": True, "message": "Logged out successfully"}

@app.get("/users/me")
async def get_current_user(authorization: str = None):
    """Get current user information."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    # Extract token from "Bearer <token>"
    if authorization.startswith("Bearer "):
        token = authorization[7:]  # Remove "Bearer " prefix
    else:
        token = authorization
    
    # Check session
    session = sessions.get(token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Get user
    user = users_db.get(session["username"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
        "is_active": user["is_active"],
        "last_login": user.get("last_login"),
        "created_at": user["created_at"]
    }

@app.get("/users")
async def list_users():
    """List all users (test version)."""
    user_list = []
    for user in users_db.values():
        user_list.append({
            "id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "role": user["role"],
            "is_active": user["is_active"],
            "created_at": user["created_at"],
            "last_login": user.get("last_login")
        })
    
    return {
        "users": user_list,
        "total": len(user_list)
    }

@app.get("/metrics")
async def get_metrics():
    """Get system metrics."""
    return {
        "total_users": len(users_db),
        "active_users": len([u for u in users_db.values() if u["is_active"]]),
        "daily_logins": 25,  # Test data
        "failed_attempts": 3,  # Test data
        "active_sessions": len(sessions),
        "timestamp": datetime.utcnow(),
        "total_incidents_today": 8,  # Test data for dashboard
        "total_collections_today": 15,  # Test data for dashboard
        "avg_completion_rate": 85.5,  # Test data for dashboard
        "active_crews": 4  # Test data for dashboard
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting SwachhGram Auth Service (Fixed Version with Username/Password)...")
    print("Available endpoints:")
    print("  GET  /")
    print("  GET  /health")
    print("  POST /auth/login")
    print("  POST /auth/logout")
    print("  GET  /users/me")
    print("  GET  /users")
    print("  GET  /metrics")
    print("\nTest Users:")
    print("  Username: admin, Password: admin123")
    print("  Username: supervisor, Password: sup123")
    print("  Username: crew, Password: crew123")
    print("  Username: citizen, Password: cit123")
    print("\nStarting server on http://localhost:8000")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
