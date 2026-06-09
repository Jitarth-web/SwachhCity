"""
Business logic services for Collection Service.
IEEE Std 830-1998 SRS compliant service layer with PostGIS operations.
"""

import json
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, text
from fastapi import HTTPException, status, UploadFile
import logging
import uuid
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import unary_union
from geoalchemy2.functions import ST_GeomFromText, ST_Distance, ST_Within, ST_AsGeoJSON
from geoalchemy2.types import WKBElement

from shared.utils import (
    upload_to_s3, compress_image, validate_gps_accuracy,
    settings, calculate_distance_km, parse_geojson_polygon,
    is_point_in_polygon
)
from .models import (
    CollectionLog, Route, RouteSegment, DailyRouteProgress,
    CollectionAnomaly, CollectionAnalytics
)
from .schemas import (
    CollectionLogCreate, CollectionLogUpdate, RouteCreate, RouteUpdate,
    RouteProgressUpdate, CollectionFilter, RouteOptimizationRequest
)

logger = logging.getLogger(__name__)


class CollectionService:
    """Collection logging service with GPS validation and route tracking."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_collection_log(self, collection_data: CollectionLogCreate,
                            photo_file: UploadFile, user_id: str) -> CollectionLog:
        """Create collection log with photo upload and GPS validation."""
        try:
            # Validate GPS accuracy
            if not validate_gps_accuracy(
                collection_data.location.latitude,
                collection_data.location.longitude,
                collection_data.location.accuracy
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="GPS accuracy too poor for accurate location tracking"
                )
            
            # Convert GPS location to PostGIS point
            point_wkt = f"POINT({collection_data.location.longitude} {collection_data.location.latitude})"
            location_geom = ST_GeomFromText(point_wkt, 4326)
            
            # Upload photo
            photo_url = self._upload_collection_photo(photo_file, str(uuid.uuid4()))
            
            # Check if location is within assigned route
            in_route = False
            route_deviation = None
            route_segment_id = None
            
            if collection_data.route_id:
                in_route, route_deviation, route_segment_id = self._validate_route_location(
                    collection_data.route_id,
                    collection_data.location.latitude,
                    collection_data.location.longitude
                )
            
            # Create collection log
            db_collection = CollectionLog(
                crew_id=collection_data.crew_id,
                truck_id=collection_data.truck_id,
                route_id=collection_data.route_id,
                weight_kg=collection_data.weight_kg,
                waste_type=collection_data.waste_type,
                volume_m3=collection_data.volume_m3,
                location=location_geom,
                location_accuracy=collection_data.location.accuracy,
                altitude=collection_data.location.altitude,
                in_route=in_route,
                route_deviation_meters=route_deviation,
                route_segment_id=route_segment_id,
                photo_url=photo_url,
                collection_time=collection_data.collection_time,
                device_id=collection_data.device_id,
                battery_level=collection_data.battery_level,
                signal_strength=collection_data.signal_strength,
                weather_conditions=collection_data.weather_conditions,
                notes=collection_data.notes
            )
            
            self.db.add(db_collection)
            self.db.commit()
            self.db.refresh(db_collection)
            
            # Update daily progress
            self._update_daily_progress(collection_data.crew_id, collection_data.route_id, db_collection)
            
            # Check for anomalies
            self._check_collection_anomalies(db_collection)
            
            # Update analytics
            self._update_collection_analytics(db_collection)
            
            logger.info(f"Created collection log {db_collection.id} for crew {collection_data.crew_id}")
            return db_collection
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create collection log: {e}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create collection log"
            )
    
    def get_collection_log(self, log_id: str) -> Optional[CollectionLog]:
        """Get collection log by ID."""
        return self.db.query(CollectionLog).filter(CollectionLog.id == log_id).first()
    
    def update_collection_log(self, log_id: str, update_data: CollectionLogUpdate,
                            user_id: str, user_role: str) -> CollectionLog:
        """Update collection log with audit trail."""
        collection = self.get_collection_log(log_id)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection log not found"
            )
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(collection, field, value)
        
        # Add verification info if provided
        if update_data.verified_by:
            collection.verified_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(collection)
        
        # Update analytics if significant changes
        if 'weight_kg' in update_dict or 'collection_quality_score' in update_dict:
            self._update_collection_analytics(collection)
        
        logger.info(f"Updated collection log {log_id} by {user_role} {user_id}")
        return collection
    
    def list_collections(self, filters: CollectionFilter, page: int = 1,
                        per_page: int = 20) -> Tuple[List[CollectionLog], int]:
        """List collection logs with filtering and pagination."""
        query = self.db.query(CollectionLog)
        
        # Apply filters
        if filters.crew_id:
            query = query.filter(CollectionLog.crew_id == filters.crew_id)
        if filters.truck_id:
            query = query.filter(CollectionLog.truck_id == filters.truck_id)
        if filters.route_id:
            query = query.filter(CollectionLog.route_id == filters.route_id)
        if filters.ward_id:
            # Filter by route's ward_id
            query = query.join(Route).filter(Route.ward_id == filters.ward_id)
        if filters.waste_type:
            query = query.filter(CollectionLog.waste_type == filters.waste_type)
        if filters.in_route is not None:
            query = query.filter(CollectionLog.in_route == filters.in_route)
        if filters.date_from:
            query = query.filter(CollectionLog.collection_time >= filters.date_from)
        if filters.date_to:
            query = query.filter(CollectionLog.collection_time <= filters.date_to)
        if filters.verified_only:
            query = query.filter(CollectionLog.verified_by.isnot(None))
        
        # Order by collection time (newest first)
        query = query.order_by(desc(CollectionLog.collection_time))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * per_page
        collections = query.offset(offset).limit(per_page).all()
        
        return collections, total
    
    def get_crew_collections_today(self, crew_id: str) -> List[CollectionLog]:
        """Get today's collections for a crew."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        return self.db.query(CollectionLog).filter(
            and_(
                CollectionLog.crew_id == crew_id,
                CollectionLog.collection_time >= today_start
            )
        ).order_by(desc(CollectionLog.collection_time)).all()
    
    def get_route_status(self, crew_id: str) -> Optional[DailyRouteProgress]:
        """Get current route status for a crew."""
        today = datetime.utcnow().date()
        
        return self.db.query(DailyRouteProgress).filter(
            and_(
                DailyRouteProgress.crew_id == crew_id,
                func.date(DailyRouteProgress.date) == today,
                DailyRouteProgress.is_active == True
            )
        ).first()
    
    def update_route_progress(self, progress_update: RouteProgressUpdate) -> DailyRouteProgress:
        """Update route progress for real-time tracking."""
        today = datetime.utcnow().date()
        
        # Get or create daily progress record
        progress = self.db.query(DailyRouteProgress).filter(
            and_(
                DailyRouteProgress.crew_id == progress_update.crew_id,
                func.date(DailyRouteProgress.date) == today
            )
        ).first()
        
        if not progress:
            progress = DailyRouteProgress(
                crew_id=progress_update.crew_id,
                route_id=progress_update.route_id,
                date=today,
                start_time=datetime.utcnow(),
                is_active=True
            )
            self.db.add(progress)
        
        # Update location
        if progress_update.current_location:
            point_wkt = f"POINT({progress_update.current_location.longitude} {progress_update.current_location.latitude})"
            progress.current_location = ST_GeomFromText(point_wkt, 4326)
            progress.last_location_update = datetime.utcnow()
        
        # Handle segment completion
        if progress_update.segment_completed:
            segment = self.db.query(RouteSegment).filter(
                RouteSegment.id == progress_update.segment_completed
            ).first()
            if segment and not segment.is_completed:
                segment.is_completed = True
                segment.completed_at = datetime.utcnow()
                progress.completed_segments += 1
        
        # Handle pause/resume
        if progress_update.is_paused is not None:
            progress.is_paused = progress_update.is_paused
            if progress_update.is_paused and progress_update.pause_reason:
                progress.pause_reason = progress_update.pause_reason
        
        # Calculate completion percentage
        if progress.total_segments > 0:
            progress.completion_percentage = (progress.completed_segments / progress.total_segments) * 100
        
        # Calculate time metrics
        if progress.start_time:
            progress.time_elapsed_minutes = (datetime.utcnow() - progress.start_time).total_seconds() / 60
        
        # Update efficiency metrics
        self._calculate_efficiency_metrics(progress)
        
        self.db.commit()
        self.db.refresh(progress)
        
        return progress
    
    def _upload_collection_photo(self, photo_file: UploadFile, log_id: str) -> str:
        """Upload collection photo to S3."""
        try:
            # Read file content
            file_content = photo_file.file.read()
            
            # Compress image
            compressed_content = compress_image(file_content, settings.IMAGE_COMPRESSION_TARGET_KB)
            
            # Generate filename
            file_extension = photo_file.filename.split('.')[-1] if '.' in photo_file.filename else 'jpg'
            filename = f"collections/{log_id}/{uuid.uuid4()}.{file_extension}"
            
            # Upload to S3
            photo_url = upload_to_s3(compressed_content, filename, photo_file.content_type)
            
            return photo_url
            
        except Exception as e:
            logger.error(f"Failed to upload collection photo: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload photo"
            )
    
    def _validate_route_location(self, route_id: str, latitude: float, longitude: float) -> Tuple[bool, Optional[float], Optional[uuid.UUID]]:
        """Validate if location is within assigned route."""
        try:
            # Get route
            route = self.db.query(Route).filter(Route.id == route_id).first()
            if not route:
                return False, None, None
            
            # Create point for collection location
            point = Point(longitude, latitude)
            
            # Check if point is within route boundary
            if route.boundary:
                # Convert PostGIS geometry to Shapely
                boundary_wkb = bytes(route.boundary.data) if isinstance(route.boundary, WKBElement) else route.boundary
                boundary_polygon = self._wkb_to_shapely(boundary_wkb)
                
                if boundary_polygon and boundary_polygon.contains(point):
                    # Find nearest route segment
                    nearest_segment = self._find_nearest_route_segment(route_id, longitude, latitude)
                    return True, 0.0, nearest_segment.id if nearest_segment else None
                else:
                    # Calculate distance from route
                    distance = boundary_polygon.distance(point) * 111320  # Convert to meters
                    return False, distance, None
            
            return False, None, None
            
        except Exception as e:
            logger.error(f"Route location validation failed: {e}")
            return False, None, None
    
    def _find_nearest_route_segment(self, route_id: str, longitude: float, latitude: float) -> Optional[RouteSegment]:
        """Find nearest route segment to given location."""
        try:
            point_wkt = f"POINT({longitude} {latitude})"
            point_geom = ST_GeomFromText(point_wkt, 4326)
            
            # Find nearest segment using PostGIS
            segment = self.db.query(RouteSegment).filter(
                RouteSegment.route_id == route_id
            ).order_by(
                func.ST_Distance(RouteSegment.geometry, point_geom)
            ).first()
            
            return segment
            
        except Exception as e:
            logger.error(f"Failed to find nearest route segment: {e}")
            return None
    
    def _wkb_to_shapely(self, wkb_data):
        """Convert WKB to Shapely geometry."""
        try:
            from shapely import wkb
            return wkb.loads(wkb_data)
        except Exception as e:
            logger.error(f"Failed to convert WKB to Shapely: {e}")
            return None
    
    def _update_daily_progress(self, crew_id: str, route_id: Optional[str], collection: CollectionLog) -> None:
        """Update daily route progress metrics."""
        try:
            today = datetime.utcnow().date()
            
            # Get or create progress record
            progress = self.db.query(DailyRouteProgress).filter(
                and_(
                    DailyRouteProgress.crew_id == crew_id,
                    func.date(DailyRouteProgress.date) == today
                )
            ).first()
            
            if not progress and route_id:
                # Get route info
                route = self.db.query(Route).filter(Route.id == route_id).first()
                total_segments = self.db.query(RouteSegment).filter(RouteSegment.route_id == route_id).count()
                
                progress = DailyRouteProgress(
                    crew_id=crew_id,
                    route_id=route_id,
                    date=today,
                    total_segments=total_segments,
                    start_time=collection.collection_time,
                    is_active=True
                )
                self.db.add(progress)
            
            if progress:
                # Update collection metrics
                progress.total_collections += 1
                progress.total_weight_kg += collection.weight_kg
                
                if progress.total_collections > 0:
                    progress.average_weight_per_collection = progress.total_weight_kg / progress.total_collections
                
                # Update time metrics
                if progress.start_time:
                    progress.time_elapsed_minutes = (collection.collection_time - progress.start_time).total_seconds() / 60
                    if progress.time_elapsed_minutes > 0:
                        progress.collections_per_hour = (progress.total_collections / progress.time_elapsed_minutes) * 60
                        progress.kg_per_hour = (progress.total_weight_kg / progress.time_elapsed_minutes) * 60
                
                # Update efficiency
                self._calculate_efficiency_metrics(progress)
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update daily progress: {e}")
    
    def _calculate_efficiency_metrics(self, progress: DailyRouteProgress) -> None:
        """Calculate efficiency metrics for route progress."""
        try:
            # Collections per hour efficiency
            target_collections_per_hour = 4.0  # Target: 4 collections per hour
            if progress.collections_per_hour > 0:
                progress.collections_per_hour = min(progress.collections_per_hour / target_collections_per_hour * 100, 100)
            
            # Weight per hour efficiency
            target_kg_per_hour = 200.0  # Target: 200 kg per hour
            if progress.kg_per_hour > 0:
                progress.kg_per_hour = min(progress.kg_per_hour / target_kg_per_hour * 100, 100)
            
            # Overall efficiency (weighted average)
            progress.efficiency_score = (progress.collections_per_hour * 0.6 + progress.kg_per_hour * 0.4)
            
        except Exception as e:
            logger.error(f"Failed to calculate efficiency metrics: {e}")
    
    def _check_collection_anomalies(self, collection: CollectionLog) -> None:
        """Check for collection anomalies and create alerts."""
        try:
            anomalies = []
            
            # Check weight anomalies
            if collection.weight_kg > 1000:  # Unusually heavy collection
                anomalies.append({
                    "type": "excessive_weight",
                    "severity": "high",
                    "description": f"Collection weight {collection.weight_kg}kg exceeds normal limits"
                })
            elif collection.weight_kg < 1.0:  # Unusually light collection
                anomalies.append({
                    "type": "insufficient_weight",
                    "severity": "medium",
                    "description": f"Collection weight {collection.weight_kg}kg seems unusually low"
                })
            
            # Check route deviation
            if not collection.in_route and collection.route_deviation_meters:
                if collection.route_deviation_meters > 500:  # More than 500m from route
                    anomalies.append({
                        "type": "route_deviation",
                        "severity": "high",
                        "description": f"Collection {collection.route_deviation_meters}m from assigned route"
                    })
            
            # Check GPS accuracy
            if collection.location_accuracy and collection.location_accuracy > 50:
                anomalies.append({
                    "type": "poor_gps_accuracy",
                    "severity": "medium",
                    "description": f"GPS accuracy {collection.location_accuracy}m may affect location accuracy"
                })
            
            # Create anomaly records
            for anomaly_data in anomalies:
                anomaly = CollectionAnomaly(
                    collection_log_id=collection.id,
                    crew_id=collection.crew_id,
                    anomaly_type=anomaly_data["type"],
                    severity=anomaly_data["severity"],
                    description=anomaly_data["description"],
                    detection_rule=f"auto_{anomaly_data['type']}"
                )
                self.db.add(anomaly)
            
            if anomalies:
                self.db.commit()
                logger.info(f"Created {len(anomalies)} anomalies for collection {collection.id}")
            
        except Exception as e:
            logger.error(f"Failed to check collection anomalies: {e}")
    
    def _update_collection_analytics(self, collection: CollectionLog) -> None:
        """Update collection analytics."""
        try:
            today = datetime.utcnow().date()
            
            # Get or create analytics record
            analytics = self.db.query(CollectionAnalytics).filter(
                and_(
                    CollectionAnalytics.crew_id == collection.crew_id,
                    func.date(CollectionAnalytics.date) == today
                )
            ).first()
            
            if not analytics:
                # Get ward_id from route
                ward_id = None
                if collection.route_id:
                    route = self.db.query(Route).filter(Route.id == collection.route_id).first()
                    ward_id = route.ward_id if route else None
                
                analytics = CollectionAnalytics(
                    crew_id=collection.crew_id,
                    route_id=collection.route_id,
                    ward_id=ward_id or uuid.uuid4(),  # Fallback
                    date=today
                )
                self.db.add(analytics)
            
            # Update metrics
            analytics.total_collections += 1
            analytics.total_weight_kg += collection.weight_kg
            analytics.avg_weight_per_collection = analytics.total_weight_kg / analytics.total_collections
            
            if collection.weight_kg > analytics.max_weight_single_collection:
                analytics.max_weight_single_collection = collection.weight_kg
            
            # Update route completion rate
            if collection.route_id:
                route_collections = self.db.query(CollectionLog).filter(
                    and_(
                        CollectionLog.route_id == collection.route_id,
                        func.date(CollectionLog.collection_time) == today
                    )
                ).count()
                
                route = self.db.query(Route).filter(Route.id == collection.route_id).first()
                if route and route.assigned_crew_id:
                    total_segments = self.db.query(RouteSegment).filter(RouteSegment.route_id == collection.route_id).count()
                    completed_segments = self.db.query(RouteSegment).filter(
                        and_(
                            RouteSegment.route_id == collection.route_id,
                            RouteSegment.is_completed == True
                        )
                    ).count()
                    
                    if total_segments > 0:
                        analytics.route_completion_rate = (completed_segments / total_segments) * 100
            
            # Update GPS accuracy
            if collection.location_accuracy:
                if analytics.avg_gps_accuracy == 0:
                    analytics.avg_gps_accuracy = collection.location_accuracy
                else:
                    analytics.avg_gps_accuracy = (analytics.avg_gps_accuracy + collection.location_accuracy) / 2
            
            # Update in-route percentage
            total_crew_collections = self.db.query(CollectionLog).filter(
                and_(
                    CollectionLog.crew_id == collection.crew_id,
                    func.date(CollectionLog.collection_time) == today
                )
            ).count()
            
            in_route_collections = self.db.query(CollectionLog).filter(
                and_(
                    CollectionLog.crew_id == collection.crew_id,
                    CollectionLog.in_route == True,
                    func.date(CollectionLog.collection_time) == today
                )
            ).count()
            
            if total_crew_collections > 0:
                analytics.in_route_percentage = (in_route_collections / total_crew_collections) * 100
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update collection analytics: {e}")


class RouteService:
    """Route management service with PostGIS operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_route(self, route_data: RouteCreate) -> Route:
        """Create new route with PostGIS geometry."""
        try:
            # Convert GeoJSON to PostGIS geometry
            boundary_wkt = self._geojson_to_wkt(route_data.boundary, "POLYGON")
            boundary_geom = ST_GeomFromText(boundary_wkt, 4326)
            
            centerline_geom = None
            if route_data.centerline:
                centerline_wkt = self._geojson_to_wkt(route_data.centerline, "LINESTRING")
                centerline_geom = ST_GeomFromText(centerline_wkt, 4326)
            
            route = Route(
                name=route_data.name,
                code=route_data.code,
                ward_id=route_data.ward_id,
                boundary=boundary_geom,
                centerline=centerline_geom,
                waypoints=route_data.waypoints,
                total_distance_km=route_data.total_distance_km,
                estimated_time_minutes=route_data.estimated_time_minutes,
                difficulty_level=route_data.difficulty_level,
                shift_start_time=route_data.shift_start_time,
                shift_end_time=route_data.shift_end_time
            )
            
            self.db.add(route)
            self.db.commit()
            self.db.refresh(route)
            
            return route
            
        except Exception as e:
            logger.error(f"Failed to create route: {e}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create route"
            )
    
    def get_route_by_id(self, route_id: str) -> Optional[Route]:
        """Get route by ID with GeoJSON conversion."""
        route = self.db.query(Route).filter(Route.id == route_id).first()
        return route
    
    def list_routes(self, ward_id: Optional[str] = None, active_only: bool = True) -> List[Route]:
        """List routes with optional filtering."""
        query = self.db.query(Route)
        
        if ward_id:
            query = query.filter(Route.ward_id == ward_id)
        if active_only:
            query = query.filter(Route.is_active == True)
        
        return query.order_by(Route.name).all()
    
    def update_route(self, route_id: str, update_data: RouteUpdate) -> Route:
        """Update route information."""
        route = self.get_route_by_id(route_id)
        if not route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Route not found"
            )
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            if field in ['boundary', 'centerline'] and value:
                # Convert GeoJSON to PostGIS geometry
                geom_type = "POLYGON" if field == 'boundary' else "LINESTRING"
                wkt = self._geojson_to_wkt(value, geom_type)
                geom = ST_GeomFromText(wkt, 4326)
                setattr(route, field, geom)
            else:
                setattr(route, field, value)
        
        self.db.commit()
        self.db.refresh(route)
        
        return route
    
    def assign_route_to_crew(self, route_id: str, crew_id: str, truck_id: str) -> Route:
        """Assign route to crew and truck."""
        route = self.get_route_by_id(route_id)
        if not route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Route not found"
            )
        
        route.assigned_crew_id = crew_id
        route.assigned_truck_id = truck_id
        
        self.db.commit()
        self.db.refresh(route)
        
        return route
    
    def _geojson_to_wkt(self, geojson_data: Dict[str, Any], geom_type: str) -> str:
        """Convert GeoJSON to WKT format."""
        try:
            if geom_type == "POLYGON":
                coordinates = geojson_data.get('coordinates', [])
                if coordinates and len(coordinates) > 0:
                    # Format: POLYGON((lng1 lat1, lng2 lat2, ...))
                    coords = coordinates[0]  # Exterior ring
                    coord_str = ", ".join([f"{point[0]} {point[1]}" for point in coords])
                    return f"POLYGON(({coord_str}))"
            
            elif geom_type == "LINESTRING":
                coordinates = geojson_data.get('coordinates', [])
                if coordinates:
                    # Format: LINESTRING(lng1 lat1, lng2 lat2, ...)
                    coord_str = ", ".join([f"{point[0]} {point[1]}" for point in coordinates])
                    return f"LINESTRING({coord_str})"
            
            raise ValueError(f"Unsupported geometry type or invalid coordinates: {geom_type}")
            
        except Exception as e:
            logger.error(f"Failed to convert GeoJSON to WKT: {e}")
            raise ValueError("Invalid GeoJSON format")
