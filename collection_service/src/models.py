"""
Database models for Collection Service.
IEEE Std 830-1998 SRS compliant data models with PostGIS support.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text, Float, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime
import uuid
from shared.models import GPSLocation

from .database import Base


class CollectionLog(Base):
    """
    Collection log model for crew operations.
    Stores waste collection data with GPS tracking and route validation.
    """
    __tablename__ = "collection_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    crew_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Crew ID")
    truck_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Truck ID")
    route_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="Assigned route ID")
    
    # Collection data
    weight_kg = Column(Float, nullable=False, comment="Weight collected in kilograms")
    waste_type = Column(String(50), nullable=True, comment="Type of waste collected")
    volume_m3 = Column(Float, nullable=True, comment="Estimated volume in cubic meters")
    
    # GPS and location data
    location = Column(Geometry('POINT', srid=4326), nullable=False, comment="GPS location as PostGIS point")
    location_accuracy = Column(Float, nullable=True, comment="GPS accuracy in meters")
    altitude = Column(Float, nullable=True, comment="Altitude in meters")
    
    # Route validation
    in_route = Column(Boolean, default=False, nullable=False, comment="Whether location is within assigned route")
    route_deviation_meters = Column(Float, nullable=True, comment="Distance from route in meters")
    route_segment_id = Column(UUID(as_uuid=True), nullable=True, comment="Current route segment")
    
    # Photo and verification
    photo_url = Column(String(500), nullable=False, comment="S3 URL of collection photo")
    photo_thumbnail_url = Column(String(500), nullable=True, comment="S3 URL of thumbnail")
    photo_verified = Column(Boolean, default=False, nullable=False, comment="Photo verification status")
    ai_confidence = Column(Float, nullable=True, comment="AI verification confidence")
    
    # Quality metrics
    collection_quality_score = Column(Float, nullable=True, comment="Collection quality score (0-100)")
    contamination_level = Column(String(20), nullable=True, comment="Contamination level (low/medium/high)")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Log creation timestamp")
    collection_time = Column(DateTime(timezone=True), nullable=False, comment="Actual collection time")
    synced_at = Column(DateTime(timezone=True), nullable=True, comment="Sync timestamp for offline logs")
    
    # Metadata
    device_id = Column(String(100), nullable=True, comment="Device identifier")
    battery_level = Column(Integer, nullable=True, comment="Device battery level")
    signal_strength = Column(Integer, nullable=True, comment="Signal strength")
    weather_conditions = Column(String(50), nullable=True, comment="Weather conditions")
    
    # Audit fields
    verified_by = Column(UUID(as_uuid=True), nullable=True, comment="Verifier ID")
    verified_at = Column(DateTime(timezone=True), nullable=True, comment="Verification timestamp")
    notes = Column(Text, nullable=True, comment="Additional notes")

    def __repr__(self):
        return f"<CollectionLog(id={self.id}, crew_id={self.crew_id}, weight_kg={self.weight_kg}, in_route={self.in_route})>"

    @property
    def latitude(self):
        """Get latitude from PostGIS point."""
        from sqlalchemy import func
        # This would be accessed via a query, not as a property
        return None

    @property
    def longitude(self):
        """Get longitude from PostGIS point."""
        from sqlalchemy import func
        # This would be accessed via a query, not as a property
        return None


class Route(Base):
    """
    Route model for crew assignments.
    Stores route polygons and optimization data.
    """
    __tablename__ = "routes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False, comment="Route name")
    code = Column(String(20), unique=True, nullable=False, comment="Route code")
    ward_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Ward ID")
    
    # Route geometry
    boundary = Column(Geometry('POLYGON', srid=4326), nullable=False, comment="Route boundary polygon")
    centerline = Column(Geometry('LINESTRING', srid=4326), nullable=True, comment="Route centerline")
    waypoints = Column(JSONB, nullable=True, comment="Route waypoints (JSON)")
    
    # Route properties
    total_distance_km = Column(Float, nullable=True, comment="Total route distance in km")
    estimated_time_minutes = Column(Integer, nullable=True, comment="Estimated completion time")
    difficulty_level = Column(String(20), default="medium", comment="Route difficulty (easy/medium/hard)")
    
    # Assignment data
    assigned_crew_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="Currently assigned crew")
    assigned_truck_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="Currently assigned truck")
    shift_start_time = Column(DateTime(timezone=True), nullable=True, comment="Shift start time")
    shift_end_time = Column(DateTime(timezone=True), nullable=True, comment="Shift end time")
    
    # Performance metrics
    avg_collection_time_minutes = Column(Float, nullable=True, comment="Average collection time")
    completion_rate = Column(Float, default=0.0, comment="Route completion rate")
    last_completed_at = Column(DateTime(timezone=True), nullable=True, comment="Last completion timestamp")
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, comment="Route active status")
    is_optimized = Column(Boolean, default=False, nullable=False, comment="Route optimization status")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")
    optimized_at = Column(DateTime(timezone=True), nullable=True, comment="Last optimization timestamp")

    def __repr__(self):
        return f"<Route(id={self.id}, name={self.name}, code={self.code}, ward_id={self.ward_id})>"


class RouteSegment(Base):
    """
    Route segment model for detailed route tracking.
    Breaks down routes into manageable segments.
    """
    __tablename__ = "route_segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_order = Column(Integer, nullable=False, comment="Segment order in route")
    
    # Segment geometry
    geometry = Column(Geometry('LINESTRING', srid=4326), nullable=False, comment="Segment geometry")
    start_point = Column(Geometry('POINT', srid=4326), nullable=False, comment="Segment start point")
    end_point = Column(Geometry('POINT', srid=4326), nullable=False, comment="Segment end point")
    
    # Segment properties
    distance_km = Column(Float, nullable=False, comment="Segment distance in km")
    estimated_time_minutes = Column(Integer, nullable=True, comment="Estimated time for segment")
    difficulty_score = Column(Float, default=1.0, comment="Segment difficulty score")
    
    # Collection points
    collection_points = Column(JSONB, nullable=True, comment="Collection points along segment")
    priority = Column(String(20), default="normal", comment="Segment priority")
    
    # Status
    is_completed = Column(Boolean, default=False, nullable=False, comment="Segment completion status")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="Completion timestamp")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")
    
    # Relationships
    route = relationship("Route", backref="segments")

    def __repr__(self):
        return f"<RouteSegment(id={self.id}, route_id={self.route_id}, sequence_order={self.sequence_order})>"


class DailyRouteProgress(Base):
    """
    Daily route progress model for real-time tracking.
    Tracks completion percentage and performance metrics.
    """
    __tablename__ = "daily_route_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    crew_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Crew ID")
    route_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Route ID")
    date = Column(DateTime(timezone=True), nullable=False, index=True, comment="Progress date")
    
    # Progress metrics
    total_segments = Column(Integer, default=0, nullable=False, comment="Total route segments")
    completed_segments = Column(Integer, default=0, nullable=False, comment="Completed segments")
    completion_percentage = Column(Float, default=0.0, comment="Completion percentage")
    
    # Collection metrics
    total_collections = Column(Integer, default=0, nullable=False, comment="Total collections")
    total_weight_kg = Column(Float, default=0.0, comment="Total weight collected")
    average_weight_per_collection = Column(Float, nullable=True, comment="Average weight per collection")
    
    # Time metrics
    start_time = Column(DateTime(timezone=True), nullable=True, comment="Route start time")
    current_time = Column(DateTime(timezone=True), nullable=True, comment="Current progress time")
    estimated_completion_time = Column(DateTime(timezone=True), nullable=True, comment="Estimated completion")
    time_elapsed_minutes = Column(Float, default=0.0, comment="Time elapsed in minutes")
    
    # Performance metrics
    collections_per_hour = Column(Float, default=0.0, comment="Collections per hour rate")
    kg_per_hour = Column(Float, default=0.0, comment="Kilograms per hour rate")
    efficiency_score = Column(Float, default=0.0, comment="Overall efficiency score")
    
    # GPS tracking
    current_location = Column(Geometry('POINT', srid=4326), nullable=True, comment="Current GPS location")
    last_location_update = Column(DateTime(timezone=True), nullable=True, comment="Last location update")
    total_distance_traveled_km = Column(Float, default=0.0, comment="Total distance traveled")
    
    # Status
    is_active = Column(Boolean, default=False, nullable=False, comment="Active route status")
    is_completed = Column(Boolean, default=False, nullable=False, comment="Route completion status")
    is_paused = Column(Boolean, default=False, nullable=False, comment="Route pause status")
    pause_reason = Column(String(200), nullable=True, comment="Pause reason")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")

    def __repr__(self):
        return f"<DailyRouteProgress(id={self.id}, crew_id={self.crew_id}, completion_percentage={self.completion_percentage})>"


class CollectionAnomaly(Base):
    """
    Collection anomaly model for quality control.
    Flags unusual collection patterns for review.
    """
    __tablename__ = "collection_anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    collection_log_id = Column(UUID(as_uuid=True), ForeignKey("collection_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    crew_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Crew ID")
    
    # Anomaly details
    anomaly_type = Column(String(50), nullable=False, comment="Type of anomaly")
    severity = Column(String(20), default="medium", comment="Severity level (low/medium/high/critical)")
    description = Column(Text, nullable=False, comment="Anomaly description")
    
    # Detection data
    detection_rule = Column(String(100), nullable=True, comment="Rule that triggered detection")
    confidence_score = Column(Float, nullable=True, comment="Detection confidence")
    affected_metrics = Column(JSONB, nullable=True, comment="Affected metrics")
    
    # Resolution
    status = Column(String(20), default="open", comment="Anomaly status (open/investigating/resolved)")
    resolved_by = Column(UUID(as_uuid=True), nullable=True, comment="Resolver ID")
    resolution_notes = Column(Text, nullable=True, comment="Resolution notes")
    resolved_at = Column(DateTime(timezone=True), nullable=True, comment="Resolution timestamp")
    
    # Notifications
    supervisor_notified = Column(Boolean, default=False, nullable=False, comment="Supervisor notification status")
    admin_notified = Column(Boolean, default=False, nullable=False, comment="Admin notification status")
    notification_sent_at = Column(DateTime(timezone=True), nullable=True, comment="Notification timestamp")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Anomaly detection timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")
    
    # Relationships
    collection_log = relationship("CollectionLog", backref="anomalies")

    def __repr__(self):
        return f"<CollectionAnomaly(id={self.id}, type={self.anomaly_type}, severity={self.severity})>"


class CollectionAnalytics(Base):
    """
    Collection analytics model for reporting and insights.
    Pre-computed analytics for dashboard performance.
    """
    __tablename__ = "collection_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    crew_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="Crew ID (null for overall)")
    route_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="Route ID (null for overall)")
    ward_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Ward ID")
    date = Column(DateTime(timezone=True), nullable=False, index=True, comment="Analytics date")
    
    # Collection metrics
    total_collections = Column(Integer, default=0, nullable=False, comment="Total collections")
    total_weight_kg = Column(Float, default=0.0, comment="Total weight collected")
    avg_weight_per_collection = Column(Float, default=0.0, comment="Average weight per collection")
    max_weight_single_collection = Column(Float, default=0.0, comment="Maximum single collection weight")
    
    # Performance metrics
    avg_collection_time_minutes = Column(Float, default=0.0, comment="Average collection time")
    collections_per_hour = Column(Float, default=0.0, comment="Collections per hour rate")
    route_completion_rate = Column(Float, default=0.0, comment="Route completion rate")
    
    # Quality metrics
    in_route_percentage = Column(Float, default=0.0, comment="Percentage of collections within route")
    avg_gps_accuracy = Column(Float, default=0.0, comment="Average GPS accuracy")
    photo_verification_rate = Column(Float, default=0.0, comment="Photo verification rate")
    
    # Anomaly metrics
    total_anomalies = Column(Integer, default=0, nullable=False, comment="Total anomalies detected")
    critical_anomalies = Column(Integer, default=0, nullable=False, comment="Critical anomalies")
    anomaly_resolution_rate = Column(Float, default=0.0, comment="Anomaly resolution rate")
    
    # Efficiency metrics
    fuel_efficiency = Column(Float, nullable=True, comment="Fuel efficiency (km/l)")
    time_efficiency = Column(Float, default=0.0, comment="Time efficiency score")
    overall_efficiency = Column(Float, default=0.0, comment="Overall efficiency score")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Analytics creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")

    def __repr__(self):
        return f"<CollectionAnalytics(id={self.id}, crew_id={self.crew_id}, date={self.date}, total_collections={self.total_collections})>"
