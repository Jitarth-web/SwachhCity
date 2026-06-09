"""
Pydantic schemas for Incident Service.
IEEE Std 830-1998 SRS compliant data validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
import uuid
from shared.models import IncidentCategory, IncidentStatus, GPSLocation


class GPSLocationSchema(BaseModel):
    """GPS location schema for incident reporting."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    accuracy: float = Field(..., gt=0, description="GPS accuracy in meters")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="GPS timestamp")

    @validator('accuracy')
    def validate_accuracy(cls, v):
        if v > 50:
            raise ValueError('GPS accuracy must be within 50 meters for automatic reporting')
        return v


class IncidentCreate(BaseModel):
    """Incident creation schema."""
    category: IncidentCategory
    location: GPSLocationSchema
    description: Optional[str] = Field(None, max_length=1000, description="Additional description")
    priority: Optional[str] = Field("medium", regex="^(low|medium|high)$", description="Priority level")

    @validator('location')
    def validate_location(cls, v):
        if v.accuracy > 50:
            raise ValueError('GPS accuracy exceeds 50 meters. Please enable high-accuracy GPS or use manual map selection.')
        return v


class IncidentUpdate(BaseModel):
    """Incident update schema."""
    status: Optional[IncidentStatus] = None
    assigned_crew_id: Optional[uuid.UUID] = None
    assigned_supervisor_id: Optional[uuid.UUID] = None
    priority: Optional[str] = Field(None, regex="^(low|medium|high)$")
    description: Optional[str] = Field(None, max_length=1000)


class IncidentResponse(BaseModel):
    """Incident response schema."""
    id: uuid.UUID
    ticket_id: str
    user_id: uuid.UUID
    category: IncidentCategory
    photo_url: str
    location: Dict[str, Any]
    ward_id: uuid.UUID
    status: IncidentStatus
    description: Optional[str]
    priority: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    assigned_crew_id: Optional[uuid.UUID]
    assigned_supervisor_id: Optional[uuid.UUID]
    assigned_at: Optional[datetime]
    gps_accuracy: Optional[float]
    image_quality_score: Optional[float]
    verified_by_ai: bool
    ai_confidence: Optional[float]
    citizen_notified: bool
    supervisor_notified: bool
    last_notification_at: Optional[datetime]
    age_hours: float
    resolution_time_hours: Optional[float]

    class Config:
        from_attributes = True


class IncidentPhotoCreate(BaseModel):
    """Incident photo creation schema."""
    photo_url: str
    thumbnail_url: Optional[str] = None
    file_size_bytes: int = Field(..., gt=0)
    width: Optional[int] = Field(None, gt=0)
    height: Optional[int] = Field(None, gt=0)
    mime_type: str = Field("image/jpeg", regex="^image/(jpeg|png|webp)$")
    is_primary: bool = False


class IncidentPhotoResponse(BaseModel):
    """Incident photo response schema."""
    id: uuid.UUID
    incident_id: uuid.UUID
    photo_url: str
    thumbnail_url: Optional[str]
    file_size_bytes: int
    width: Optional[int]
    height: Optional[int]
    mime_type: str
    ai_category: Optional[str]
    ai_confidence: Optional[float]
    objects_detected: Optional[Dict[str, Any]]
    analysis_timestamp: Optional[datetime]
    uploaded_at: datetime
    is_primary: bool

    class Config:
        from_attributes = True


class IncidentCommentCreate(BaseModel):
    """Incident comment creation schema."""
    comment: str = Field(..., min_length=1, max_length=2000)
    is_internal: bool = False
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None


class IncidentCommentResponse(BaseModel):
    """Incident comment response schema."""
    id: uuid.UUID
    incident_id: uuid.UUID
    user_id: uuid.UUID
    user_role: str
    comment: str
    is_internal: bool
    attachment_url: Optional[str]
    attachment_type: Optional[str]
    created_at: datetime
    updated_at: datetime
    citizen_visible: bool
    edited: bool

    class Config:
        from_attributes = True


class IncidentStatusHistoryResponse(BaseModel):
    """Incident status history response schema."""
    id: uuid.UUID
    incident_id: uuid.UUID
    old_status: Optional[IncidentStatus]
    new_status: IncidentStatus
    changed_by: uuid.UUID
    changed_by_role: str
    reason: Optional[str]
    changed_at: datetime
    system_generated: bool

    class Config:
        from_attributes = True


class WardCreate(BaseModel):
    """Ward creation schema."""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    boundary: Dict[str, Any] = Field(..., description="GeoJSON polygon boundary")
    center_latitude: float = Field(..., ge=-90, le=90)
    center_longitude: float = Field(..., ge=-180, le=180)
    sla_hours: int = Field(6, gt=0, le=168)
    supervisor_id: Optional[uuid.UUID] = None


class WardResponse(BaseModel):
    """Ward response schema."""
    id: uuid.UUID
    name: str
    code: str
    boundary: Dict[str, Any]
    center_latitude: float
    center_longitude: float
    sla_hours: int
    supervisor_id: Optional[uuid.UUID]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IncidentAnalyticsResponse(BaseModel):
    """Incident analytics response schema."""
    id: uuid.UUID
    ward_id: uuid.UUID
    date: datetime
    total_incidents: int
    open_incidents: int
    resolved_incidents: int
    escalated_incidents: int
    black_spot_count: int
    overflowing_bin_count: int
    illegal_dumping_count: int
    avg_resolution_time_hours: float
    citizen_satisfaction_score: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IncidentFilter(BaseModel):
    """Incident filter schema for queries."""
    status: Optional[IncidentStatus] = None
    category: Optional[IncidentCategory] = None
    ward_id: Optional[uuid.UUID] = None
    priority: Optional[str] = Field(None, regex="^(low|medium|high)$")
    user_id: Optional[uuid.UUID] = None
    assigned_crew_id: Optional[uuid.UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    is_resolved: Optional[bool] = None


class IncidentListResponse(BaseModel):
    """Incident list response schema."""
    incidents: List[IncidentResponse]
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
    s3_connection: str


class MetricsResponse(BaseModel):
    """Metrics response schema."""
    total_incidents: int
    open_incidents: int
    resolved_today: int
    avg_resolution_time_hours: float
    incidents_by_category: Dict[str, int]
    incidents_by_ward: Dict[str, int]
    sla_breach_rate: float


class NotificationRequest(BaseModel):
    """Notification request schema."""
    user_id: uuid.UUID
    incident_id: uuid.UUID
    notification_type: str = Field(..., regex="^(status_update|assignment|resolution|escalation)$")
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None


class BulkIncidentUpdate(BaseModel):
    """Bulk incident update schema."""
    incident_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)
    updates: IncidentUpdate


class IncidentExport(BaseModel):
    """Incident export schema."""
    format: str = Field("csv", regex="^(csv|excel|json)$")
    filters: Optional[IncidentFilter] = None
    include_photos: bool = False


class IncidentMapData(BaseModel):
    """Incident map data schema for GIS visualization."""
    incidents: List[Dict[str, Any]]
    wards: List[Dict[str, Any]]
    heatmap_data: List[Dict[str, Any]]
    total_count: int
