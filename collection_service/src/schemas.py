"""
Pydantic schemas for Collection Service.
IEEE Std 830-1998 SRS compliant data validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
import uuid
from shared.models import GPSLocation


class GPSLocationSchema(BaseModel):
    """GPS location schema for collection logging."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    accuracy: float = Field(..., gt=0, description="GPS accuracy in meters")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="GPS timestamp")

    @validator('accuracy')
    def validate_accuracy(cls, v):
        if v > 100:  # Allow higher accuracy for collection logs
            raise ValueError('GPS accuracy should be within 100 meters for accurate location tracking')
        return v


class CollectionLogCreate(BaseModel):
    """Collection log creation schema."""
    crew_id: uuid.UUID
    truck_id: uuid.UUID
    route_id: Optional[uuid.UUID] = None
    weight_kg: float = Field(..., gt=0, le=10000, description="Weight collected in kilograms")
    waste_type: Optional[str] = Field(None, max_length=50, description="Type of waste collected")
    volume_m3: Optional[float] = Field(None, gt=0, le=100, description="Estimated volume in cubic meters")
    location: GPSLocationSchema
    collection_time: datetime = Field(default_factory=datetime.utcnow, description="Actual collection time")
    device_id: Optional[str] = Field(None, max_length=100, description="Device identifier")
    battery_level: Optional[int] = Field(None, ge=0, le=100, description="Device battery level")
    signal_strength: Optional[int] = Field(None, ge=-120, le=0, description="Signal strength in dBm")
    weather_conditions: Optional[str] = Field(None, max_length=50, description="Weather conditions")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")

    @validator('weight_kg')
    def validate_weight(cls, v):
        if v < 0.1:  # Minimum realistic weight
            raise ValueError('Weight must be at least 0.1 kg')
        if v > 5000:  # Maximum realistic weight for single collection
            raise ValueError('Weight exceeds maximum realistic limit')
        return v


class CollectionLogUpdate(BaseModel):
    """Collection log update schema."""
    weight_kg: Optional[float] = Field(None, gt=0, le=10000)
    waste_type: Optional[str] = Field(None, max_length=50)
    volume_m3: Optional[float] = Field(None, gt=0, le=100)
    notes: Optional[str] = Field(None, max_length=1000)
    verified_by: Optional[uuid.UUID] = None
    collection_quality_score: Optional[float] = Field(None, ge=0, le=100)
    contamination_level: Optional[str] = Field(None, regex="^(low|medium|high)$")


class CollectionLogResponse(BaseModel):
    """Collection log response schema."""
    id: uuid.UUID
    crew_id: uuid.UUID
    truck_id: uuid.UUID
    route_id: Optional[uuid.UUID]
    weight_kg: float
    waste_type: Optional[str]
    volume_m3: Optional[float]
    location: Dict[str, Any]  # PostGIS point as JSON
    location_accuracy: Optional[float]
    altitude: Optional[float]
    in_route: bool
    route_deviation_meters: Optional[float]
    route_segment_id: Optional[uuid.UUID]
    photo_url: str
    photo_thumbnail_url: Optional[str]
    photo_verified: bool
    ai_confidence: Optional[float]
    collection_quality_score: Optional[float]
    contamination_level: Optional[str]
    created_at: datetime
    collection_time: datetime
    synced_at: Optional[datetime]
    device_id: Optional[str]
    battery_level: Optional[int]
    signal_strength: Optional[int]
    weather_conditions: Optional[str]
    verified_by: Optional[uuid.UUID]
    verified_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


class RouteCreate(BaseModel):
    """Route creation schema."""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    ward_id: uuid.UUID
    boundary: Dict[str, Any] = Field(..., description="GeoJSON polygon boundary")
    centerline: Optional[Dict[str, Any]] = Field(None, description="GeoJSON centerline")
    waypoints: Optional[List[Dict[str, Any]]] = None
    total_distance_km: Optional[float] = Field(None, gt=0)
    estimated_time_minutes: Optional[int] = Field(None, gt=0)
    difficulty_level: str = Field("medium", regex="^(easy|medium|hard)$")
    shift_start_time: Optional[datetime] = None
    shift_end_time: Optional[datetime] = None


class RouteUpdate(BaseModel):
    """Route update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    boundary: Optional[Dict[str, Any]] = None
    centerline: Optional[Dict[str, Any]] = None
    waypoints: Optional[List[Dict[str, Any]]] = None
    total_distance_km: Optional[float] = Field(None, gt=0)
    estimated_time_minutes: Optional[int] = Field(None, gt=0)
    difficulty_level: Optional[str] = Field(None, regex="^(easy|medium|hard)$")
    assigned_crew_id: Optional[uuid.UUID] = None
    assigned_truck_id: Optional[uuid.UUID] = None
    shift_start_time: Optional[datetime] = None
    shift_end_time: Optional[datetime] = None
    is_active: Optional[bool] = None


class RouteResponse(BaseModel):
    """Route response schema."""
    id: uuid.UUID
    name: str
    code: str
    ward_id: uuid.UUID
    boundary: Dict[str, Any]
    centerline: Optional[Dict[str, Any]]
    waypoints: Optional[List[Dict[str, Any]]]
    total_distance_km: Optional[float]
    estimated_time_minutes: Optional[int]
    difficulty_level: str
    assigned_crew_id: Optional[uuid.UUID]
    assigned_truck_id: Optional[uuid.UUID]
    shift_start_time: Optional[datetime]
    shift_end_time: Optional[datetime]
    avg_collection_time_minutes: Optional[float]
    completion_rate: float
    last_completed_at: Optional[datetime]
    is_active: bool
    is_optimized: bool
    created_at: datetime
    updated_at: datetime
    optimized_at: Optional[datetime]

    class Config:
        from_attributes = True


class RouteSegmentCreate(BaseModel):
    """Route segment creation schema."""
    route_id: uuid.UUID
    sequence_order: int = Field(..., gt=0)
    geometry: Dict[str, Any] = Field(..., description="GeoJSON linestring")
    start_point: Dict[str, Any] = Field(..., description="GeoJSON point")
    end_point: Dict[str, Any] = Field(..., description="GeoJSON point")
    distance_km: float = Field(..., gt=0)
    estimated_time_minutes: Optional[int] = Field(None, gt=0)
    difficulty_score: float = Field(1.0, ge=0.1, le=10.0)
    collection_points: Optional[List[Dict[str, Any]]] = None
    priority: str = Field("normal", regex="^(low|normal|high|critical)$")


class RouteSegmentResponse(BaseModel):
    """Route segment response schema."""
    id: uuid.UUID
    route_id: uuid.UUID
    sequence_order: int
    geometry: Dict[str, Any]
    start_point: Dict[str, Any]
    end_point: Dict[str, Any]
    distance_km: float
    estimated_time_minutes: Optional[int]
    difficulty_score: float
    collection_points: Optional[List[Dict[str, Any]]]
    priority: str
    is_completed: bool
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DailyRouteProgressResponse(BaseModel):
    """Daily route progress response schema."""
    id: uuid.UUID
    crew_id: uuid.UUID
    route_id: uuid.UUID
    date: datetime
    total_segments: int
    completed_segments: int
    completion_percentage: float
    total_collections: int
    total_weight_kg: float
    average_weight_per_collection: Optional[float]
    start_time: Optional[datetime]
    current_time: Optional[datetime]
    estimated_completion_time: Optional[datetime]
    time_elapsed_minutes: float
    collections_per_hour: float
    kg_per_hour: float
    efficiency_score: float
    current_location: Optional[Dict[str, Any]]
    last_location_update: Optional[datetime]
    total_distance_traveled_km: float
    is_active: bool
    is_completed: bool
    is_paused: bool
    pause_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CollectionAnomalyResponse(BaseModel):
    """Collection anomaly response schema."""
    id: uuid.UUID
    collection_log_id: uuid.UUID
    crew_id: uuid.UUID
    anomaly_type: str
    severity: str
    description: str
    detection_rule: Optional[str]
    confidence_score: Optional[float]
    affected_metrics: Optional[Dict[str, Any]]
    status: str
    resolved_by: Optional[uuid.UUID]
    resolution_notes: Optional[str]
    resolved_at: Optional[datetime]
    supervisor_notified: bool
    admin_notified: bool
    notification_sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CollectionAnalyticsResponse(BaseModel):
    """Collection analytics response schema."""
    id: uuid.UUID
    crew_id: Optional[uuid.UUID]
    route_id: Optional[uuid.UUID]
    ward_id: uuid.UUID
    date: datetime
    total_collections: int
    total_weight_kg: float
    avg_weight_per_collection: float
    max_weight_single_collection: float
    avg_collection_time_minutes: float
    collections_per_hour: float
    route_completion_rate: float
    in_route_percentage: float
    avg_gps_accuracy: float
    photo_verification_rate: float
    total_anomalies: int
    critical_anomalies: int
    anomaly_resolution_rate: float
    fuel_efficiency: Optional[float]
    time_efficiency: float
    overall_efficiency: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RouteStatusResponse(BaseModel):
    """Route status response schema for crew dashboard."""
    route_id: uuid.UUID
    route_name: str
    crew_id: uuid.UUID
    completion_percentage: float
    collections_today: int
    weight_collected_today: float
    estimated_completion_time: Optional[datetime]
    current_location: Optional[Dict[str, Any]]
    is_active: bool
    is_paused: bool
    last_update: datetime


class RouteProgressUpdate(BaseModel):
    """Route progress update schema."""
    crew_id: uuid.UUID
    route_id: uuid.UUID
    current_location: Optional[GPSLocationSchema] = None
    segment_completed: Optional[uuid.UUID] = None
    is_paused: Optional[bool] = None
    pause_reason: Optional[str] = None


class CollectionFilter(BaseModel):
    """Collection filter schema for queries."""
    crew_id: Optional[uuid.UUID] = None
    truck_id: Optional[uuid.UUID] = None
    route_id: Optional[uuid.UUID] = None
    ward_id: Optional[uuid.UUID] = None
    waste_type: Optional[str] = None
    in_route: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    verified_only: Optional[bool] = None


class CollectionListResponse(BaseModel):
    """Collection list response schema."""
    collections: List[CollectionLogResponse]
    total: int
    page: int
    per_page: int
    pages: int


class APIResponse(BaseModel):
    """Standard API response schema."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthCheck(BaseModel):
    """Health check response schema."""
    status: str
    timestamp: datetime
    version: str
    database: str
    postgis: str
    s3_connection: str


class MetricsResponse(BaseModel):
    """Metrics response schema."""
    total_collections_today: int
    total_weight_today: float
    active_crews: int
    avg_completion_rate: float
    total_anomalies_today: int
    in_route_percentage: float
    avg_gps_accuracy: float


class BulkCollectionUpdate(BaseModel):
    """Bulk collection update schema."""
    collection_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)
    updates: CollectionLogUpdate


class RouteOptimizationRequest(BaseModel):
    """Route optimization request schema."""
    route_id: uuid.UUID
    crew_id: uuid.UUID
    truck_id: uuid.UUID
    current_location: GPSLocationSchema
    pending_collections: List[Dict[str, Any]]
    optimization_preferences: Optional[Dict[str, Any]] = None


class RouteOptimizationResponse(BaseModel):
    """Route optimization response schema."""
    optimized_route: List[Dict[str, Any]]
    estimated_time_reduction: Optional[float]
    estimated_fuel_savings: Optional[float]
    optimization_confidence: float
    applied_at: datetime
