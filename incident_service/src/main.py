"""
FastAPI application for Incident Service.
IEEE Std 830-1998 SRS compliant REST API.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import uuid

from shared.middleware import get_standard_middleware, get_current_user, require_role
from shared.utils import verify_jwt_token, settings
from .database import get_db, create_tables
from .models import Incident, Ward
from .schemas import (
    IncidentCreate, IncidentUpdate, IncidentResponse, IncidentFilter,
    IncidentPhotoCreate, IncidentPhotoResponse,
    IncidentCommentCreate, IncidentCommentResponse,
    IncidentStatusHistoryResponse, WardCreate, WardResponse,
    IncidentListResponse, APIResponse, HealthCheck, MetricsResponse,
    NotificationRequest, BulkIncidentUpdate, IncidentMapData
)
from .services import IncidentService, WardService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SwachhGram Incident Service",
    description="Incident Reporting Service for SwachhGram Waste Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Apply standard middleware
app = get_standard_middleware(app, allowed_origins=["http://localhost:3000"])

# Security
security = HTTPBearer()

# Dependency injection
def get_incident_service(db: Session = Depends(get_db)) -> IncidentService:
    """Get incident service instance."""
    return IncidentService(db)

def get_ward_service(db: Session = Depends(get_db)) -> WardService:
    """Get ward service instance."""
    return WardService(db)


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
        s3_connection="connected"  # TODO: Add actual S3 health check
    )


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "ward_supervisor", "zonal_commissioner"]))
):
    """Get system metrics."""
    incident_service = IncidentService(db)
    
    # Get basic metrics
    total_incidents = db.query(Incident).count()
    open_incidents = db.query(Incident).filter(Incident.status == "open").count()
    resolved_today = db.query(Incident).filter(
        Incident.status == "resolved",
        Incident.resolved_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()
    
    # Calculate average resolution time
    resolved_incidents = db.query(Incident).filter(
        Incident.status == "resolved",
        Incident.resolved_at.isnot(None)
    ).all()
    
    avg_resolution_time = 0.0
    if resolved_incidents:
        total_time = sum(inc.resolution_time_hours or 0 for inc in resolved_incidents)
        avg_resolution_time = total_time / len(resolved_incidents)
    
    # Category breakdown
    incidents_by_category = {}
    from shared.models import IncidentCategory
    for category in IncidentCategory:
        count = db.query(Incident).filter(Incident.category == category).count()
        incidents_by_category[category.value] = count
    
    # Ward breakdown
    incidents_by_ward = {}
    wards = db.query(Ward).all()
    for ward in wards:
        count = db.query(Incident).filter(Incident.ward_id == ward.id).count()
        incidents_by_ward[ward.name] = count
    
    # SLA breach rate
    sla_breached = 0
    for incident in resolved_incidents:
        if incident.resolution_time_hours and incident.resolution_time_hours > 6:  # Default SLA
            sla_breached += 1
    
    sla_breach_rate = (sla_breached / len(resolved_incidents) * 100) if resolved_incidents else 0.0
    
    return MetricsResponse(
        total_incidents=total_incidents,
        open_incidents=open_incidents,
        resolved_today=resolved_today,
        avg_resolution_time_hours=avg_resolution_time,
        incidents_by_category=incidents_by_category,
        incidents_by_ward=incidents_by_ward,
        sla_breach_rate=sla_breach_rate
    )


# Incident endpoints
@app.post("/incidents", response_model=IncidentResponse)
async def create_incident(
    incident_data: IncidentCreate,
    photo: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["citizen"])),
    incident_service: IncidentService = Depends(get_incident_service)
):
    """Create new incident with photo upload."""
    try:
        incident = incident_service.create_incident(
            incident_data=incident_data,
            user_id=current_user["user_id"],
            photo_file=photo
        )
        return IncidentResponse.from_orm(incident)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create incident failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create incident"
        )


@app.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: str,
    current_user: dict = Depends(get_current_user),
    incident_service: IncidentService = Depends(get_incident_service)
):
    """Get incident by ID."""
    try:
        incident = incident_service.get_incident_by_id(incident_id, current_user["user_id"])
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found"
            )
        return IncidentResponse.from_orm(incident)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get incident failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get incident"
        )


@app.get("/incidents/ticket/{ticket_id}", response_model=IncidentResponse)
async def get_incident_by_ticket(
    ticket_id: str,
    current_user: dict = Depends(get_current_user),
    incident_service: IncidentService = Depends(get_incident_service)
):
    """Get incident by ticket ID."""
    try:
        incident = incident_service.get_incident_by_ticket_id(ticket_id, current_user["user_id"])
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found"
            )
        return IncidentResponse.from_orm(incident)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get incident by ticket failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get incident"
        )


@app.put("/incidents/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: str,
    incident_update: IncidentUpdate,
    current_user: dict = Depends(get_current_user),
    incident_service: IncidentService = Depends(get_incident_service)
):
    """Update incident."""
    try:
        incident = incident_service.update_incident(
            incident_id=incident_id,
            incident_update=incident_update,
            user_id=current_user["user_id"],
            user_role=current_user["role"]
        )
        return IncidentResponse.from_orm(incident)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update incident failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update incident"
        )


@app.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    category: Optional[str] = None,
    ward_id: Optional[str] = None,
    priority: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user),
    incident_service: IncidentService = Depends(get_incident_service)
):
    """List incidents with filtering."""
    try:
        filters = IncidentFilter(
            status=status,
            category=category,
            ward_id=ward_id,
            priority=priority,
            date_from=date_from,
            date_to=date_to
        )
        
        incidents, total = incident_service.list_incidents(filters, page, per_page)
        
        return IncidentListResponse(
            incidents=[IncidentResponse.from_orm(incident) for incident in incidents],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page
        )
    except Exception as e:
        logger.error(f"List incidents failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list incidents"
        )


@app.get("/incidents/my", response_model=IncidentListResponse)
async def get_my_incidents(
    page: int = 1,
    per_page: int = 20,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["citizen"])),
    incident_service: IncidentService = Depends(get_incident_service)
):
    """Get current user's incidents."""
    try:
        incidents, total = incident_service.get_user_incidents(
            user_id=current_user["user_id"],
            page=page,
            per_page=per_page
        )
        
        return IncidentListResponse(
            incidents=[IncidentResponse.from_orm(incident) for incident in incidents],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page
        )
    except Exception as e:
        logger.error(f"Get user incidents failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user incidents"
        )


# Comment endpoints
@app.post("/incidents/{incident_id}/comments", response_model=IncidentCommentResponse)
async def add_comment(
    incident_id: str,
    comment_data: IncidentCommentCreate,
    current_user: dict = Depends(get_current_user),
    incident_service: IncidentService = Depends(get_incident_service)
):
    """Add comment to incident."""
    try:
        comment = incident_service.add_comment(
            incident_id=incident_id,
            comment_data=comment_data,
            user_id=current_user["user_id"],
            user_role=current_user["role"]
        )
        return IncidentCommentResponse.from_orm(comment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add comment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add comment"
        )


@app.get("/incidents/{incident_id}/comments", response_model=List[IncidentCommentResponse])
async def get_incident_comments(
    incident_id: str,
    include_internal: bool = False,
    current_user: dict = Depends(get_current_user),
    incident_service: IncidentService = Depends(get_incident_service)
):
    """Get incident comments."""
    try:
        # Determine if user can see internal comments
        can_see_internal = current_user["role"] in ["admin", "ward_supervisor", "zonal_commissioner"]
        
        comments = incident_service.get_incident_comments(
            incident_id=incident_id,
            user_id=current_user["user_id"],
            include_internal=include_internal and can_see_internal
        )
        
        return [IncidentCommentResponse.from_orm(comment) for comment in comments]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get incident comments failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get incident comments"
        )


@app.get("/incidents/{incident_id}/history", response_model=List[IncidentStatusHistoryResponse])
async def get_incident_history(
    incident_id: str,
    current_user: dict = Depends(get_current_user),
    incident_service: IncidentService = Depends(get_incident_service)
):
    """Get incident status history."""
    try:
        history = incident_service.get_incident_status_history(incident_id)
        return [IncidentStatusHistoryResponse.from_orm(record) for record in history]
    except Exception as e:
        logger.error(f"Get incident history failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get incident history"
        )


# Ward management endpoints
@app.post("/wards", response_model=WardResponse)
async def create_ward(
    ward_data: WardCreate,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "zonal_commissioner"])),
    ward_service: WardService = Depends(get_ward_service)
):
    """Create new ward."""
    try:
        ward = ward_service.create_ward(ward_data)
        return WardResponse.from_orm(ward)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create ward failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ward"
        )


@app.get("/wards", response_model=List[WardResponse])
async def list_wards(
    active_only: bool = True,
    current_user: dict = Depends(get_current_user),
    ward_service: WardService = Depends(get_ward_service)
):
    """List all wards."""
    try:
        wards = ward_service.list_wards(active_only=active_only)
        return [WardResponse.from_orm(ward) for ward in wards]
    except Exception as e:
        logger.error(f"List wards failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list wards"
        )


@app.get("/wards/{ward_id}", response_model=WardResponse)
async def get_ward(
    ward_id: str,
    current_user: dict = Depends(get_current_user),
    ward_service: WardService = Depends(get_ward_service)
):
    """Get ward by ID."""
    try:
        ward = ward_service.get_ward_by_id(ward_id)
        if not ward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ward not found"
            )
        return WardResponse.from_orm(ward)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get ward failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get ward"
        )


# Map data endpoints
@app.get("/map/data", response_model=IncidentMapData)
async def get_map_data(
    ward_id: Optional[str] = None,
    status: Optional[str] = None,
    days: int = 30,
    current_user: dict = Depends(get_current_user),
    incident_service: IncidentService = Depends(get_incident_service),
    ward_service: WardService = Depends(get_ward_service)
):
    """Get incident data for map visualization."""
    try:
        db = incident_service.db
        
        # Get incidents
        query = db.query(Incident)
        
        if ward_id:
            query = query.filter(Incident.ward_id == ward_id)
        if status:
            query = query.filter(Incident.status == status)
        
        # Filter by date range
        from_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Incident.created_at >= from_date)
        
        incidents = query.all()
        
        # Convert to map format
        incident_data = []
        for incident in incidents:
            incident_data.append({
                "id": str(incident.id),
                "ticket_id": incident.ticket_id,
                "category": incident.category.value,
                "status": incident.status.value,
                "priority": incident.priority,
                "latitude": incident.location["latitude"],
                "longitude": incident.location["longitude"],
                "created_at": incident.created_at.isoformat(),
                "ward_id": str(incident.ward_id)
            })
        
        # Get wards
        wards = ward_service.list_wards(active_only=True)
        ward_data = []
        for ward in wards:
            ward_data.append({
                "id": str(ward.id),
                "name": ward.name,
                "code": ward.code,
                "boundary": ward.boundary,
                "center": [ward.center_latitude, ward.center_longitude]
            })
        
        # Generate heatmap data (simplified)
        heatmap_data = []
        for incident in incidents:
            heatmap_data.append({
                "lat": incident.location["latitude"],
                "lng": incident.location["longitude"],
                "weight": 1.0 if incident.priority == "high" else 0.7 if incident.priority == "medium" else 0.5
            })
        
        return IncidentMapData(
            incidents=incident_data,
            wards=ward_data,
            heatmap_data=heatmap_data,
            total_count=len(incidents)
        )
    except Exception as e:
        logger.error(f"Get map data failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get map data"
        )


# Bulk operations endpoints
@app.put("/incidents/bulk", response_model=APIResponse)
async def bulk_update_incidents(
    bulk_update: BulkIncidentUpdate,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "ward_supervisor"])),
    incident_service: IncidentService = Depends(get_incident_service)
):
    """Bulk update incidents."""
    try:
        updated_count = 0
        errors = []
        
        for incident_id in bulk_update.incident_ids:
            try:
                incident_service.update_incident(
                    incident_id=incident_id,
                    incident_update=bulk_update.updates,
                    user_id=current_user["user_id"],
                    user_role=current_user["role"]
                )
                updated_count += 1
            except Exception as e:
                errors.append(f"Failed to update {incident_id}: {str(e)}")
        
        return APIResponse(
            success=True,
            message=f"Updated {updated_count} incidents",
            data={
                "updated_count": updated_count,
                "total_requested": len(bulk_update.incident_ids),
                "errors": errors
            }
        )
    except Exception as e:
        logger.error(f"Bulk update incidents failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk update incidents"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
