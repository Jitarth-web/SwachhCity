"""
FastAPI application for Collection Service.
IEEE Std 830-1998 SRS compliant REST API with PostGIS support.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import uuid

from shared.middleware import get_standard_middleware, get_current_user, require_role
from shared.utils import verify_jwt_token, settings
from .database import get_db, create_tables, create_postgis_extension
from .models import CollectionLog, Route, DailyRouteProgress
from .schemas import (
    CollectionLogCreate, CollectionLogUpdate, CollectionLogResponse,
    RouteCreate, RouteUpdate, RouteResponse, RouteProgressUpdate,
    RouteStatusResponse, CollectionFilter, CollectionListResponse,
    APIResponse, HealthCheck, MetricsResponse, BulkCollectionUpdate
)
from .services import CollectionService, RouteService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SwachhGram Collection Service",
    description="Collection Logging Service for SwachhGram Waste Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Apply standard middleware
app = get_standard_middleware(app, allowed_origins=["http://localhost:3000"])

# Security
security = HTTPBearer()

# Dependency injection
def get_collection_service(db: Session = Depends(get_db)) -> CollectionService:
    """Get collection service instance."""
    return CollectionService(db)

def get_route_service(db: Session = Depends(get_db)) -> RouteService:
    """Get route service instance."""
    return RouteService(db)


@app.on_event("startup")
async def startup_event():
    """Initialize database and PostGIS extension on startup."""
    try:
        create_postgis_extension()
        create_tables()
        logger.info("Database tables and PostGIS extension created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")


# Health check endpoints
@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        database="connected",  # TODO: Add actual DB health check
        postgis="connected",  # TODO: Add actual PostGIS health check
        s3_connection="connected"  # TODO: Add actual S3 health check
    )


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "ward_supervisor", "zonal_commissioner"]))
):
    """Get system metrics."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get today's collections
    total_collections_today = db.query(CollectionLog).filter(
        CollectionLog.collection_time >= today_start
    ).count()
    
    # Get today's weight
    total_weight_result = db.query(func.sum(CollectionLog.weight_kg)).filter(
        CollectionLog.collection_time >= today_start
    ).scalar()
    total_weight_today = total_weight_result or 0.0
    
    # Get active crews
    active_crews = db.query(DailyRouteProgress).filter(
        and_(
            DailyRouteProgress.is_active == True,
            func.date(DailyRouteProgress.date) == datetime.utcnow().date()
        )
    ).count()
    
    # Get average completion rate
    avg_completion_result = db.query(func.avg(DailyRouteProgress.completion_percentage)).filter(
        func.date(DailyRouteProgress.date) == datetime.utcnow().date()
    ).scalar()
    avg_completion_rate = avg_completion_result or 0.0
    
    # Get today's anomalies
    from .models import CollectionAnomaly
    total_anomalies_today = db.query(CollectionAnomaly).filter(
        func.date(CollectionAnomaly.created_at) == datetime.utcnow().date()
    ).count()
    
    # Get in-route percentage
    in_route_collections = db.query(CollectionLog).filter(
        and_(
            CollectionLog.in_route == True,
            CollectionLog.collection_time >= today_start
        )
    ).count()
    
    in_route_percentage = (in_route_collections / total_collections_today * 100) if total_collections_today > 0 else 0.0
    
    # Get average GPS accuracy
    avg_gps_result = db.query(func.avg(CollectionLog.location_accuracy)).filter(
        CollectionLog.collection_time >= today_start
    ).scalar()
    avg_gps_accuracy = avg_gps_result or 0.0
    
    return MetricsResponse(
        total_collections_today=total_collections_today,
        total_weight_today=total_weight_today,
        active_crews=active_crews,
        avg_completion_rate=avg_completion_rate,
        total_anomalies_today=total_anomalies_today,
        in_route_percentage=in_route_percentage,
        avg_gps_accuracy=avg_gps_accuracy
    )


# Collection log endpoints
@app.post("/logs", response_model=CollectionLogResponse)
async def create_collection_log(
    collection_data: CollectionLogCreate,
    photo: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["crew"])),
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Create new collection log with photo upload."""
    try:
        collection = collection_service.create_collection_log(
            collection_data=collection_data,
            photo_file=photo,
            user_id=current_user["user_id"]
        )
        return CollectionLogResponse.from_orm(collection)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create collection log failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create collection log"
        )


@app.get("/logs/{log_id}", response_model=CollectionLogResponse)
async def get_collection_log(
    log_id: str,
    current_user: dict = Depends(get_current_user),
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Get collection log by ID."""
    try:
        collection = collection_service.get_collection_log(log_id)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection log not found"
            )
        
        # Check access permissions
        if current_user["role"] == "crew" and collection.crew_id != uuid.UUID(current_user["user_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return CollectionLogResponse.from_orm(collection)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get collection log failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get collection log"
        )


@app.put("/logs/{log_id}", response_model=CollectionLogResponse)
async def update_collection_log(
    log_id: str,
    update_data: CollectionLogUpdate,
    current_user: dict = Depends(get_current_user),
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Update collection log."""
    try:
        collection = collection_service.update_collection_log(
            log_id=log_id,
            update_data=update_data,
            user_id=current_user["user_id"],
            user_role=current_user["role"]
        )
        return CollectionLogResponse.from_orm(collection)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update collection log failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update collection log"
        )


@app.get("/logs", response_model=CollectionListResponse)
async def list_collection_logs(
    page: int = 1,
    per_page: int = 20,
    crew_id: Optional[str] = None,
    truck_id: Optional[str] = None,
    route_id: Optional[str] = None,
    ward_id: Optional[str] = None,
    waste_type: Optional[str] = None,
    in_route: Optional[bool] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    verified_only: Optional[bool] = None,
    current_user: dict = Depends(get_current_user),
    collection_service: CollectionService = Depends(get_collection_service)
):
    """List collection logs with filtering."""
    try:
        filters = CollectionFilter(
            crew_id=uuid.UUID(crew_id) if crew_id else None,
            truck_id=uuid.UUID(truck_id) if truck_id else None,
            route_id=uuid.UUID(route_id) if route_id else None,
            ward_id=uuid.UUID(ward_id) if ward_id else None,
            waste_type=waste_type,
            in_route=in_route,
            date_from=date_from,
            date_to=date_to,
            verified_only=verified_only
        )
        
        collections, total = collection_service.list_collections(filters, page, per_page)
        
        return CollectionListResponse(
            collections=[CollectionLogResponse.from_orm(collection) for collection in collections],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page
        )
    except Exception as e:
        logger.error(f"List collection logs failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list collection logs"
        )


@app.get("/logs/my", response_model=List[CollectionLogResponse])
async def get_my_collections(
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["crew"])),
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Get current crew's collections for today."""
    try:
        collections = collection_service.get_crew_collections_today(current_user["user_id"])
        return [CollectionLogResponse.from_orm(collection) for collection in collections]
    except Exception as e:
        logger.error(f"Get my collections failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get your collections"
        )


# Route status endpoints
@app.get("/routes/status", response_model=RouteStatusResponse)
async def get_route_status(
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["crew"])),
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Get current route status for crew."""
    try:
        progress = collection_service.get_route_status(current_user["user_id"])
        if not progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active route found"
            )
        
        # Get route name
        route = collection_service.db.query(Route).filter(Route.id == progress.route_id).first()
        
        # Get today's collections
        collections = collection_service.get_crew_collections_today(current_user["user_id"])
        
        return RouteStatusResponse(
            route_id=progress.route_id,
            route_name=route.name if route else "Unknown Route",
            crew_id=progress.crew_id,
            completion_percentage=progress.completion_percentage,
            collections_today=len(collections),
            weight_collected_today=progress.total_weight_kg,
            estimated_completion_time=progress.estimated_completion_time,
            current_location={
                "latitude": progress.current_location.y if progress.current_location else None,
                "longitude": progress.current_location.x if progress.current_location else None
            } if progress.current_location else None,
            is_active=progress.is_active,
            is_paused=progress.is_paused,
            last_update=progress.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get route status failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get route status"
        )


@app.put("/routes/progress", response_model=APIResponse)
async def update_route_progress(
    progress_update: RouteProgressUpdate,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["crew"])),
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Update route progress for real-time tracking."""
    try:
        progress = collection_service.update_route_progress(progress_update)
        
        return APIResponse(
            success=True,
            message="Route progress updated successfully",
            data={
                "completion_percentage": progress.completion_percentage,
                "is_active": progress.is_active,
                "is_paused": progress.is_paused
            }
        )
    except Exception as e:
        logger.error(f"Update route progress failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update route progress"
        )


# Route management endpoints
@app.post("/routes", response_model=RouteResponse)
async def create_route(
    route_data: RouteCreate,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "ward_supervisor"])),
    route_service: RouteService = Depends(get_route_service)
):
    """Create new route."""
    try:
        route = route_service.create_route(route_data)
        return RouteResponse.from_orm(route)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create route failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create route"
        )


@app.get("/routes", response_model=List[RouteResponse])
async def list_routes(
    ward_id: Optional[str] = None,
    active_only: bool = True,
    current_user: dict = Depends(get_current_user),
    route_service: RouteService = Depends(get_route_service)
):
    """List routes."""
    try:
        routes = route_service.list_routes(
            ward_id=uuid.UUID(ward_id) if ward_id else None,
            active_only=active_only
        )
        return [RouteResponse.from_orm(route) for route in routes]
    except Exception as e:
        logger.error(f"List routes failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list routes"
        )


@app.get("/routes/{route_id}", response_model=RouteResponse)
async def get_route(
    route_id: str,
    current_user: dict = Depends(get_current_user),
    route_service: RouteService = Depends(get_route_service)
):
    """Get route by ID."""
    try:
        route = route_service.get_route_by_id(route_id)
        if not route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Route not found"
            )
        return RouteResponse.from_orm(route)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get route failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get route"
        )


@app.put("/routes/{route_id}", response_model=RouteResponse)
async def update_route(
    route_id: str,
    update_data: RouteUpdate,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "ward_supervisor"])),
    route_service: RouteService = Depends(get_route_service)
):
    """Update route."""
    try:
        route = route_service.update_route(route_id, update_data)
        return RouteResponse.from_orm(route)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update route failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update route"
        )


@app.put("/routes/{route_id}/assign", response_model=RouteResponse)
async def assign_route_to_crew(
    route_id: str,
    crew_id: str,
    truck_id: str,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "ward_supervisor"])),
    route_service: RouteService = Depends(get_route_service)
):
    """Assign route to crew and truck."""
    try:
        route = route_service.assign_route_to_crew(route_id, crew_id, truck_id)
        return RouteResponse.from_orm(route)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assign route failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign route"
        )


# Bulk operations endpoints
@app.put("/logs/bulk", response_model=APIResponse)
async def bulk_update_collections(
    bulk_update: BulkCollectionUpdate,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "ward_supervisor"])),
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Bulk update collection logs."""
    try:
        updated_count = 0
        errors = []
        
        for collection_id in bulk_update.collection_ids:
            try:
                collection_service.update_collection_log(
                    log_id=str(collection_id),
                    update_data=bulk_update.updates,
                    user_id=current_user["user_id"],
                    user_role=current_user["role"]
                )
                updated_count += 1
            except Exception as e:
                errors.append(f"Failed to update {collection_id}: {str(e)}")
        
        return APIResponse(
            success=True,
            message=f"Updated {updated_count} collection logs",
            data={
                "updated_count": updated_count,
                "total_requested": len(bulk_update.collection_ids),
                "errors": errors
            }
        )
    except Exception as e:
        logger.error(f"Bulk update collections failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk update collections"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
