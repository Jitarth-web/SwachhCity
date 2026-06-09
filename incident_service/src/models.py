"""
Database models for Incident Service.
IEEE Std 830-1998 SRS compliant data models.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from shared.models import IncidentCategory, IncidentStatus, GPSLocation

from .database import Base


class Incident(Base):
    """
    Incident model for citizen reporting.
    Stores waste management incidents with GIS metadata.
    """
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    ticket_id = Column(String(50), unique=True, nullable=False, index=True, comment="Unique ticket ID (SWC-YYYYMMDD-XXXXX)")
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Reporting citizen ID")
    category = Column(Enum(IncidentCategory), nullable=False, index=True, comment="Incident category")
    photo_url = Column(String(500), nullable=False, comment="S3 URL of incident photo")
    location = Column(JSONB, nullable=False, comment="GPS location data as JSON")
    ward_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Ward ID where incident occurred")
    status = Column(Enum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN, index=True, comment="Incident status")
    description = Column(Text, nullable=True, comment="Additional description from citizen")
    priority = Column(String(20), default="medium", nullable=False, comment="Priority level (low/medium/high)")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Incident creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")
    resolved_at = Column(DateTime(timezone=True), nullable=True, comment="Resolution timestamp")
    
    # Assignment fields
    assigned_crew_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="Assigned crew ID")
    assigned_supervisor_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="Assigned supervisor ID")
    assigned_at = Column(DateTime(timezone=True), nullable=True, comment="Assignment timestamp")
    
    # Quality and metadata
    gps_accuracy = Column(Float, nullable=True, comment="GPS accuracy in meters")
    image_quality_score = Column(Float, nullable=True, comment="AI-generated image quality score")
    verified_by_ai = Column(Boolean, default=False, nullable=False, comment="AI verification status")
    ai_confidence = Column(Float, nullable=True, comment="AI classification confidence")
    
    # Communication tracking
    citizen_notified = Column(Boolean, default=False, nullable=False, comment="Citizen notified of status")
    supervisor_notified = Column(Boolean, default=False, nullable=False, comment="Supervisor notified")
    last_notification_at = Column(DateTime(timezone=True), nullable=True, comment="Last notification timestamp")

    def __repr__(self):
        return f"<Incident(id={self.id}, ticket_id={self.ticket_id}, category={self.category}, status={self.status})>"

    @property
    def is_resolved(self):
        """Check if incident is resolved."""
        return self.status == IncidentStatus.RESOLVED

    @property
    def resolution_time_hours(self):
        """Calculate resolution time in hours."""
        if not self.resolved_at:
            return None
        return (self.resolved_at - self.created_at).total_seconds() / 3600

    @property
    def age_hours(self):
        """Calculate incident age in hours."""
        return (datetime.utcnow() - self.created_at.replace(tzinfo=None)).total_seconds() / 3600


class IncidentPhoto(Base):
    """
    Incident photo model for multiple photo support.
    Stores photo metadata and analysis results.
    """
    __tablename__ = "incident_photos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    photo_url = Column(String(500), nullable=False, comment="S3 URL of photo")
    thumbnail_url = Column(String(500), nullable=True, comment="S3 URL of thumbnail")
    file_size_bytes = Column(Integer, nullable=False, comment="File size in bytes")
    width = Column(Integer, nullable=True, comment="Image width in pixels")
    height = Column(Integer, nullable=True, comment="Image height in pixels")
    mime_type = Column(String(50), nullable=False, default="image/jpeg", comment="MIME type")
    
    # AI analysis results
    ai_category = Column(String(50), nullable=True, comment="AI-detected waste category")
    ai_confidence = Column(Float, nullable=True, comment="AI classification confidence")
    objects_detected = Column(JSONB, nullable=True, comment="AI-detected objects (JSON)")
    analysis_timestamp = Column(DateTime(timezone=True), nullable=True, comment="AI analysis timestamp")
    
    # Metadata
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Upload timestamp")
    is_primary = Column(Boolean, default=False, nullable=False, comment="Primary photo flag")
    
    # Relationship
    incident = relationship("Incident", backref="photos")

    def __repr__(self):
        return f"<IncidentPhoto(id={self.id}, incident_id={self.incident_id}, is_primary={self.is_primary})>"


class IncidentComment(Base):
    """
    Incident comment model for communication tracking.
    Stores comments from citizens, crew, and supervisors.
    """
    __tablename__ = "incident_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Comment author ID")
    user_role = Column(String(50), nullable=False, comment="Comment author role")
    comment = Column(Text, nullable=False, comment="Comment content")
    is_internal = Column(Boolean, default=False, nullable=False, comment="Internal comment (not visible to citizen)")
    
    # Attachments
    attachment_url = Column(String(500), nullable=True, comment="Attachment URL")
    attachment_type = Column(String(50), nullable=True, comment="Attachment type")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Comment timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Edit timestamp")
    
    # Metadata
    citizen_visible = Column(Boolean, default=True, nullable=False, comment="Visible to citizen")
    edited = Column(Boolean, default=False, nullable=False, comment="Comment edited flag")
    
    # Relationships
    incident = relationship("Incident", backref="comments")

    def __repr__(self):
        return f"<IncidentComment(id={self.id}, incident_id={self.incident_id}, user_role={self.user_role})>"


class IncidentStatusHistory(Base):
    """
    Incident status history model for audit trail.
    Tracks all status changes with timestamps and reasons.
    """
    __tablename__ = "incident_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = Column(Enum(IncidentStatus), nullable=True, comment="Previous status")
    new_status = Column(Enum(IncidentStatus), nullable=False, comment="New status")
    changed_by = Column(UUID(as_uuid=True), nullable=False, index=True, comment="User who made the change")
    changed_by_role = Column(String(50), nullable=False, comment="Role of user who made the change")
    reason = Column(Text, nullable=True, comment="Reason for status change")
    
    # Timestamps
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Status change timestamp")
    
    # Metadata
    system_generated = Column(Boolean, default=False, nullable=False, comment="System-generated status change")
    
    # Relationships
    incident = relationship("Incident", backref="status_history")

    def __repr__(self):
        return f"<IncidentStatusHistory(id={self.id}, incident_id={self.incident_id}, old_status={self.old_status}, new_status={self.new_status})>"


class IncidentAnalytics(Base):
    """
    Incident analytics model for reporting and insights.
    Pre-computed analytics for dashboard performance.
    """
    __tablename__ = "incident_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    ward_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Ward ID")
    date = Column(DateTime(timezone=True), nullable=False, index=True, comment="Analytics date (UTC)")
    
    # Counts
    total_incidents = Column(Integer, default=0, nullable=False, comment="Total incidents")
    open_incidents = Column(Integer, default=0, nullable=False, comment="Open incidents")
    resolved_incidents = Column(Integer, default=0, nullable=False, comment="Resolved incidents")
    escalated_incidents = Column(Integer, default=0, nullable=False, comment="Escalated incidents")
    
    # Category breakdown
    black_spot_count = Column(Integer, default=0, nullable=False, comment="Black spot incidents")
    overflowing_bin_count = Column(Integer, default=0, nullable=False, comment="Overflowing bin incidents")
    illegal_dumping_count = Column(Integer, default=0, nullable=False, comment="Illegal dumping incidents")
    
    # Performance metrics
    avg_resolution_time_hours = Column(Float, default=0.0, nullable=False, comment="Average resolution time")
    citizen_satisfaction_score = Column(Float, nullable=True, comment="Citizen satisfaction score")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Analytics creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")

    def __repr__(self):
        return f"<IncidentAnalytics(id={self.id}, ward_id={self.ward_id}, date={self.date}, total_incidents={self.total_incidents})>"


class Ward(Base):
    """
    Ward model for geographical boundaries.
    Stores ward information with GIS polygons.
    """
    __tablename__ = "wards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False, comment="Ward name")
    code = Column(String(20), unique=True, nullable=False, comment="Ward code")
    boundary = Column(JSONB, nullable=False, comment="GeoJSON polygon boundary")
    center_latitude = Column(Float, nullable=False, comment="Ward center latitude")
    center_longitude = Column(Float, nullable=False, comment="Ward center longitude")
    
    # Configuration
    sla_hours = Column(Integer, default=6, nullable=False, comment="SLA in hours")
    supervisor_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="Ward supervisor ID")
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, comment="Ward active status")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")

    def __repr__(self):
        return f"<Ward(id={self.id}, name={self.name}, code={self.code})>"

    @property
    def is_sla_breached(self, incident_age_hours):
        """Check if SLA is breached for given incident age."""
        return incident_age_hours > self.sla_hours
