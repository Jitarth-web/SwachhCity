"""
Shared Data Server for SwachhGram - Persistent Database Version
Provides a centralized data store with SQLite database persistence
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging
import sqlite3
import json
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DB_FILE = "swachhgram.db"

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create incidents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL,
            address TEXT,
            location TEXT NOT NULL,
            photo_url TEXT NOT NULL,
            reported_by TEXT NOT NULL,
            reporter_name TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            assigned_to TEXT,
            weight_collected REAL,
            completion_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    # Create crews table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crews (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            current_location TEXT,
            last_location_update TEXT,
            collections_today INTEGER DEFAULT 0,
            avg_time REAL DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

# Initialize database on startup
init_database()

# Initialize FastAPI app
app = FastAPI(
    title="SwachhGram Shared Data Server",
    description="Centralized data store for SwachhGram applications with persistent storage",
    version="2.0.0"
)

# Apply CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class IncidentCreate(BaseModel):
    category: str
    description: str
    severity: str
    address: str = None
    location: dict
    photo_url: str
    reported_by: str
    reporter_name: str

class IncidentUpdate(BaseModel):
    status: str = None
    assigned_to: str = None
    weight_collected: float = None
    completion_notes: str = None
    started_at: str = None
    completed_at: str = None

class CrewCreate(BaseModel):
    id: str
    name: str
    status: str
    current_location: dict = None
    last_location_update: str = None
    collections_today: int = 0
    avg_time: float = 0

# Database helper functions
def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Enable dictionary-like access
    return conn

def load_incidents_from_db():
    """Load all incidents from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents ORDER BY created_at DESC")
    incidents = []
    
    for row in cursor.fetchall():
        incident = dict(row)
        # Parse JSON fields
        incident['location'] = json.loads(incident['location'])
        incidents.append(incident)
    
    conn.close()
    return incidents

def load_crews_from_db():
    """Load all crews from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM crews")
    crews = []
    
    for row in cursor.fetchall():
        crew = dict(row)
        # Parse JSON fields
        if crew['current_location']:
            crew['current_location'] = json.loads(crew['current_location'])
        crews.append(crew)
    
    conn.close()
    return crews

def save_incident_to_db(incident_data):
    """Save incident to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO incidents 
        (id, category, description, severity, address, location, photo_url, reported_by, reporter_name, status, assigned_to, weight_collected, completion_notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        incident_data['id'],
        incident_data['category'],
        incident_data['description'],
        incident_data['severity'],
        incident_data['address'],
        json.dumps(incident_data['location']),
        incident_data['photo_url'],
        incident_data['reported_by'],
        incident_data['reporter_name'],
        incident_data.get('status', 'pending'),
        incident_data.get('assigned_to'),
        incident_data.get('weight_collected'),
        incident_data.get('completion_notes'),
        incident_data['created_at'],
        incident_data['updated_at']
    ))
    
    conn.commit()
    conn.close()

def save_crew_to_db(crew_data):
    """Save crew to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO crews 
        (id, name, status, current_location, last_location_update, collections_today, avg_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        crew_data['id'],
        crew_data['name'],
        crew_data['status'],
        json.dumps(crew_data['current_location']) if crew_data['current_location'] else None,
        crew_data['last_location_update'],
        crew_data['collections_today'],
        crew_data['avg_time']
    ))
    
    conn.commit()
    conn.close()

def init_default_crews():
    """Initialize default crews if database is empty"""
    crews = load_crews_from_db()
    if len(crews) == 0:
        logger.info("Initializing default crews...")
        default_crews = [
            {
                "id": "crew-001",
                "name": "Team Alpha",
                "status": "active",
                "current_location": {"latitude": 12.9716, "longitude": 77.5946, "accuracy": 10},
                "last_location_update": datetime.utcnow().isoformat(),
                "collections_today": 0,
                "avg_time": 0
            },
            {
                "id": "crew-002",
                "name": "Team Beta",
                "status": "active",
                "current_location": {"latitude": 12.9452, "longitude": 77.6145, "accuracy": 15},
                "last_location_update": datetime.utcnow().isoformat(),
                "collections_today": 0,
                "avg_time": 0
            },
            {
                "id": "crew-003",
                "name": "Team Gamma",
                "status": "active",
                "current_location": {"latitude": 12.9886, "longitude": 77.5906, "accuracy": 12},
                "last_location_update": datetime.utcnow().isoformat(),
                "collections_today": 0,
                "avg_time": 0
            }
        ]
        
        for crew in default_crews:
            save_crew_to_db(crew)
        
        logger.info(f"Initialized {len(default_crews)} default crews")

# Initialize default crews
init_default_crews()

# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "SwachhGram Shared Data Server is running",
        "version": "2.0.0",
        "database": "SQLite",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/incidents")
async def get_incidents():
    """Get all incidents"""
    try:
        incidents = load_incidents_from_db()
        return {"incidents": incidents}
    except Exception as e:
        logger.error(f"Error loading incidents: {e}")
        raise HTTPException(status_code=500, detail="Failed to load incidents")

@app.post("/incidents")
async def create_incident(incident: IncidentCreate):
    """Create a new incident"""
    try:
        incident_data = {
            "id": f"INC-{uuid.uuid4().hex[:8]}",
            "category": incident.category,
            "description": incident.description,
            "severity": incident.severity,
            "address": incident.address,
            "location": incident.location,
            "photo_url": incident.photo_url,
            "reported_by": incident.reported_by,
            "reporter_name": incident.reporter_name,
            "status": "pending",
            "assigned_to": None,
            "weight_collected": None,
            "completion_notes": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        save_incident_to_db(incident_data)
        logger.info(f"Created incident: {incident_data['id']}")
        
        return incident_data
    except Exception as e:
        logger.error(f"Error creating incident: {e}")
        raise HTTPException(status_code=500, detail="Failed to create incident")

@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Get a specific incident"""
    try:
        incidents = load_incidents_from_db()
        incident = next((inc for inc in incidents if inc["id"] == incident_id), None)
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        return incident
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get incident")

@app.put("/incidents/{incident_id}")
async def update_incident(incident_id: str, update: IncidentUpdate):
    """Update an incident"""
    try:
        incidents = load_incidents_from_db()
        incident = next((inc for inc in incidents if inc["id"] == incident_id), None)
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Update fields
        if update.status is not None:
            incident["status"] = update.status
            # Add timestamps based on status
            if update.status == "in_progress" and "started_at" not in incident:
                incident["started_at"] = datetime.utcnow().isoformat()
            elif update.status == "completed" and "completed_at" not in incident:
                incident["completed_at"] = datetime.utcnow().isoformat()
        if update.assigned_to is not None:
            incident["assigned_to"] = update.assigned_to
        if update.weight_collected is not None:
            incident["weight_collected"] = update.weight_collected
        if update.completion_notes is not None:
            incident["completion_notes"] = update.completion_notes
        
        # Add started_at if provided in request
        if update.started_at is not None:
            incident["started_at"] = update.started_at
        
        # Add completed_at if provided in request
        if update.completed_at is not None:
            incident["completed_at"] = update.completed_at
        
        incident["updated_at"] = datetime.utcnow().isoformat()
        
        save_incident_to_db(incident)
        logger.info(f"Updated incident: {incident_id}")
        
        return incident
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update incident")

@app.post("/incidents/{incident_id}/assign")
async def assign_incident(incident_id: str, crew_id: str = None):
    """Assign incident to a crew"""
    try:
        incidents = load_incidents_from_db()
        incident = next((inc for inc in incidents if inc["id"] == incident_id), None)
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        incident["assigned_to"] = crew_id
        incident["status"] = "assigned"
        incident["updated_at"] = datetime.utcnow().isoformat()
        
        save_incident_to_db(incident)
        logger.info(f"Assigned incident {incident_id} to crew {crew_id}")
        
        return {"message": f"Incident {incident_id} assigned to {crew_id}", "incident": incident}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign incident")

@app.get("/crews")
async def get_crews():
    """Get all crews"""
    try:
        crews = load_crews_from_db()
        return {"crews": crews}
    except Exception as e:
        logger.error(f"Error loading crews: {e}")
        raise HTTPException(status_code=500, detail="Failed to load crews")

@app.post("/crews")
async def create_crew(crew: CrewCreate):
    """Create a new crew"""
    try:
        crew_data = crew.dict()
        if not crew_data.get('last_location_update'):
            crew_data['last_location_update'] = datetime.utcnow().isoformat()
        
        save_crew_to_db(crew_data)
        logger.info(f"Created crew: {crew_data['id']}")
        
        return crew_data
    except Exception as e:
        logger.error(f"Error creating crew: {e}")
        raise HTTPException(status_code=500, detail="Failed to create crew")

@app.put("/crews/{crew_id}/location")
async def update_crew_location(crew_id: str, location: dict):
    """Update crew location"""
    try:
        crews = load_crews_from_db()
        crew = next((c for c in crews if c["id"] == crew_id), None)
        
        if not crew:
            raise HTTPException(status_code=404, detail="Crew not found")
        
        crew["current_location"] = location
        crew["last_location_update"] = datetime.utcnow().isoformat()
        
        save_crew_to_db(crew)
        logger.info(f"Updated location for crew {crew_id}")
        
        return {"message": f"Location updated for crew {crew_id}", "crew": crew}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating crew location {crew_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update crew location")

@app.get("/crews/{crew_id}/incidents")
async def get_crew_incidents(crew_id: str):
    """Get incidents assigned to a specific crew"""
    try:
        incidents = load_incidents_from_db()
        crew_incidents = [
            inc for inc in incidents 
            if inc.get("assigned_to") == crew_id or inc.get("assigned_to") is None
        ]
        return {"incidents": crew_incidents}
    except Exception as e:
        logger.error(f"Error getting crew incidents: {e}")
        raise HTTPException(status_code=500, detail="Failed to get crew incidents")

@app.delete("/incidents/{incident_id}")
async def delete_incident(incident_id: str):
    """Delete an incident"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM incidents WHERE id = ?", (incident_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
        
        conn.close()
        logger.info(f"Deleted incident: {incident_id}")
        
        return {"message": f"Incident {incident_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete incident")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting SwachhGram Shared Data Server with persistent storage...")
    logger.info(f"Database file: {os.path.abspath(DB_FILE)}")
    uvicorn.run(app, host="0.0.0.0", port=8006)
