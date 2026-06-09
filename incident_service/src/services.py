"""
Business logic services for Incident Service.
IEEE Std 830-1998 SRS compliant service layer.
"""

import hashlib
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from fastapi import HTTPException, status, UploadFile
import logging
import uuid
import io
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from shared.utils import (
    upload_to_s3, compress_image, generate_ticket_id,
    validate_gps_accuracy, send_fcm_notification, settings,
    parse_geojson_polygon, is_point_in_polygon
)
from shared.models import IncidentCategory, IncidentStatus
from .models import (
    Incident, IncidentPhoto, IncidentComment, IncidentStatusHistory,
    IncidentAnalytics, Ward
)
from .schemas import (
    IncidentCreate, IncidentUpdate, IncidentPhotoCreate,
    IncidentCommentCreate, WardCreate, IncidentFilter
)

logger = logging.getLogger(__name__)


class IncidentService:
    """Incident management service."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_incident(self, incident_data: IncidentCreate, user_id: str,
                      photo_file: UploadFile) -> Incident:
        """Create new incident with photo upload."""
        try:
            # Validate GPS accuracy
            if not validate_gps_accuracy(
                incident_data.location.latitude,
                incident_data.location.longitude,
                incident_data.location.accuracy
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="GPS accuracy exceeds 50 meters. Please enable high-accuracy GPS."
                )
            
            # Determine ward from GPS coordinates
            ward = self._get_ward_from_coordinates(
                incident_data.location.latitude,
                incident_data.location.longitude
            )
            if not ward:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Incident location is outside defined ward boundaries."
                )
            
            # Generate unique ticket ID
            ticket_id = generate_ticket_id()
            
            # Process and upload photo
            photo_url = self._upload_incident_photo(photo_file, ticket_id)
            
            # Create incident record
            db_incident = Incident(
                ticket_id=ticket_id,
                user_id=user_id,
                category=incident_data.category,
                photo_url=photo_url,
                location=incident_data.location.dict(),
                ward_id=ward.id,
                status=IncidentStatus.OPEN,
                description=incident_data.description,
                priority=incident_data.priority or "medium",
                gps_accuracy=incident_data.location.accuracy
            )
            
            self.db.add(db_incident)
            self.db.commit()
            self.db.refresh(db_incident)
            
            # Create photo record
            photo_record = IncidentPhoto(
                incident_id=db_incident.id,
                photo_url=photo_url,
                file_size_bytes=photo_file.size,
                is_primary=True
            )
            self.db.add(photo_record)
            self.db.commit()
            
            # Create status history
            self._create_status_history(
                incident_id=db_incident.id,
                old_status=None,
                new_status=IncidentStatus.OPEN,
                changed_by=user_id,
                changed_by_role="citizen",
                reason="Incident created by citizen"
            )
            
            # Auto-notify ward supervisor
            self._notify_ward_supervisor(db_incident, ward)
            
            # Update analytics
            self._update_incident_analytics(ward.id)
            
            logger.info(f"Created incident {ticket_id} for user {user_id}")
            return db_incident
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create incident: {e}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create incident"
            )
    
    def get_incident_by_id(self, incident_id: str, user_id: Optional[str] = None) -> Optional[Incident]:
        """Get incident by ID with access control."""
        incident = self.db.query(Incident).filter(Incident.id == incident_id).first()
        
        if not incident:
            return None
        
        # Check access permissions
        if user_id:
            # Citizens can only see their own incidents
            # Staff can see incidents in their ward
            # Admin can see all incidents
            if incident.user_id != user_id:
                # TODO: Implement role-based access check
                pass
        
        return incident
    
    def get_incident_by_ticket_id(self, ticket_id: str, user_id: Optional[str] = None) -> Optional[Incident]:
        """Get incident by ticket ID."""
        incident = self.db.query(Incident).filter(Incident.ticket_id == ticket_id).first()
        
        if not incident:
            return None
        
        # Apply same access control as get_incident_by_id
        if user_id and incident.user_id != user_id:
            # TODO: Implement role-based access check
            pass
        
        return incident
    
    def update_incident(self, incident_id: str, incident_update: IncidentUpdate,
                       user_id: str, user_role: str) -> Incident:
        """Update incident with status change tracking."""
        incident = self.get_incident_by_id(incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found"
            )
        
        old_status = incident.status
        
        # Update fields
        update_data = incident_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(incident, field, value)
        
        # Handle status change
        if 'status' in update_data:
            new_status = update_data['status']
            
            # Set resolved timestamp if resolved
            if new_status == IncidentStatus.RESOLVED:
                incident.resolved_at = datetime.utcnow()
            
            # Create status history
            self._create_status_history(
                incident_id=incident.id,
                old_status=old_status,
                new_status=new_status,
                changed_by=user_id,
                changed_by_role=user_role,
                reason=f"Status changed to {new_status.value}"
            )
            
            # Notify citizen if resolved
            if new_status == IncidentStatus.RESOLVED:
                self._notify_citizen_resolution(incident)
        
        self.db.commit()
        self.db.refresh(incident)
        
        # Update analytics
        self._update_incident_analytics(incident.ward_id)
        
        logger.info(f"Updated incident {incident.ticket_id} by {user_role} {user_id}")
        return incident
    
    def list_incidents(self, filters: IncidentFilter, page: int = 1,
                     per_page: int = 20) -> Tuple[List[Incident], int]:
        """List incidents with filtering and pagination."""
        query = self.db.query(Incident)
        
        # Apply filters
        if filters.status:
            query = query.filter(Incident.status == filters.status)
        if filters.category:
            query = query.filter(Incident.category == filters.category)
        if filters.ward_id:
            query = query.filter(Incident.ward_id == filters.ward_id)
        if filters.priority:
            query = query.filter(Incident.priority == filters.priority)
        if filters.user_id:
            query = query.filter(Incident.user_id == filters.user_id)
        if filters.assigned_crew_id:
            query = query.filter(Incident.assigned_crew_id == filters.assigned_crew_id)
        if filters.date_from:
            query = query.filter(Incident.created_at >= filters.date_from)
        if filters.date_to:
            query = query.filter(Incident.created_at <= filters.date_to)
        if filters.is_resolved is not None:
            if filters.is_resolved:
                query = query.filter(Incident.status == IncidentStatus.RESOLVED)
            else:
                query = query.filter(Incident.status != IncidentStatus.RESOLVED)
        
        # Order by creation date (newest first)
        query = query.order_by(desc(Incident.created_at))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * per_page
        incidents = query.offset(offset).limit(per_page).all()
        
        return incidents, total
    
    def get_user_incidents(self, user_id: str, page: int = 1,
                          per_page: int = 20) -> Tuple[List[Incident], int]:
        """Get incidents for a specific user (citizen view)."""
        query = self.db.query(Incident).filter(Incident.user_id == user_id)
        query = query.order_by(desc(Incident.created_at))
        
        total = query.count()
        offset = (page - 1) * per_page
        incidents = query.offset(offset).limit(per_page).all()
        
        return incidents, total
    
    def add_comment(self, incident_id: str, comment_data: IncidentCommentCreate,
                   user_id: str, user_role: str) -> IncidentComment:
        """Add comment to incident."""
        incident = self.get_incident_by_id(incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found"
            )
        
        comment = IncidentComment(
            incident_id=incident_id,
            user_id=user_id,
            user_role=user_role,
            comment=comment_data.comment,
            is_internal=comment_data.is_internal,
            attachment_url=comment_data.attachment_url,
            attachment_type=comment_data.attachment_type,
            citizen_visible=not comment_data.is_internal
        )
        
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        
        # Notify relevant parties
        self._notify_comment_added(incident, comment)
        
        return comment
    
    def get_incident_comments(self, incident_id: str, user_id: Optional[str] = None,
                           include_internal: bool = False) -> List[IncidentComment]:
        """Get comments for an incident."""
        incident = self.get_incident_by_id(incident_id, user_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found"
            )
        
        query = self.db.query(IncidentComment).filter(IncidentComment.incident_id == incident_id)
        
        # Filter internal comments based on user role
        if not include_internal:
            query = query.filter(IncidentComment.is_internal == False)
        
        query = query.order_by(IncidentComment.created_at)
        return query.all()
    
    def get_incident_status_history(self, incident_id: str) -> List[IncidentStatusHistory]:
        """Get status history for an incident."""
        return self.db.query(IncidentStatusHistory).filter(
            IncidentStatusHistory.incident_id == incident_id
        ).order_by(desc(IncidentStatusHistory.changed_at)).all()
    
    def _upload_incident_photo(self, photo_file: UploadFile, ticket_id: str) -> str:
        """Upload incident photo to S3."""
        try:
            # Read file content
            file_content = photo_file.file.read()
            
            # Compress image
            compressed_content = compress_image(file_content, settings.IMAGE_COMPRESSION_TARGET_KB)
            
            # Generate filename
            file_extension = photo_file.filename.split('.')[-1] if '.' in photo_file.filename else 'jpg'
            filename = f"incidents/{ticket_id}/{uuid.uuid4()}.{file_extension}"
            
            # Upload to S3
            photo_url = upload_to_s3(compressed_content, filename, photo_file.content_type)
            
            return photo_url
            
        except Exception as e:
            logger.error(f"Failed to upload incident photo: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload photo"
            )
    
    def _get_ward_from_coordinates(self, latitude: float, longitude: float) -> Optional[Ward]:
        """Get ward from GPS coordinates."""
        point = Point(longitude, latitude)
        
        # Query all active wards
        wards = self.db.query(Ward).filter(Ward.is_active == True).all()
        
        for ward in wards:
            try:
                # Parse GeoJSON boundary
                boundary_data = json.loads(ward.boundary) if isinstance(ward.boundary, str) else ward.boundary
                polygon = parse_geojson_polygon(boundary_data)
                
                if is_point_in_polygon(point, polygon):
                    return ward
            except Exception as e:
                logger.error(f"Error parsing ward boundary for {ward.name}: {e}")
                continue
        
        return None
    
    def _create_status_history(self, incident_id: str, old_status: Optional[IncidentStatus],
                            new_status: IncidentStatus, changed_by: str,
                            changed_by_role: str, reason: Optional[str] = None) -> None:
        """Create status history record."""
        history = IncidentStatusHistory(
            incident_id=incident_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            changed_by_role=changed_by_role,
            reason=reason
        )
        self.db.add(history)
        self.db.commit()
    
    def _notify_ward_supervisor(self, incident: Incident, ward: Ward) -> None:
        """Notify ward supervisor about new incident."""
        if not ward.supervisor_id:
            logger.warning(f"No supervisor assigned to ward {ward.name}")
            return
        
        try:
            # Get supervisor device token (this would come from user service)
            # For now, we'll just log the notification
            title = "New Incident Reported"
            message = f"Incident {incident.ticket_id} reported in {ward.name}"
            
            # Send FCM notification
            success = send_fcm_notification(
                token="",  # Would get from user service
                title=title,
                message=message,
                data={
                    "incident_id": str(incident.id),
                    "ticket_id": incident.ticket_id,
                    "category": incident.category.value,
                    "priority": incident.priority
                }
            )
            
            if success:
                incident.supervisor_notified = True
                incident.last_notification_at = datetime.utcnow()
                self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to notify ward supervisor: {e}")
    
    def _notify_citizen_resolution(self, incident: Incident) -> None:
        """Notify citizen about incident resolution."""
        try:
            title = "Incident Resolved"
            message = f"Your incident {incident.ticket_id} has been resolved"
            
            # Send FCM notification
            success = send_fcm_notification(
                token="",  # Would get from user service
                title=title,
                message=message,
                data={
                    "incident_id": str(incident.id),
                    "ticket_id": incident.ticket_id,
                    "status": "resolved"
                }
            )
            
            if success:
                incident.citizen_notified = True
                incident.last_notification_at = datetime.utcnow()
                self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to notify citizen: {e}")
    
    def _notify_comment_added(self, incident: Incident, comment: IncidentComment) -> None:
        """Notify relevant parties about new comment."""
        try:
            # Determine who should be notified based on comment type
            if comment.is_internal:
                # Notify staff
                recipients = [incident.assigned_crew_id, incident.assigned_supervisor_id]
            else:
                # Notify citizen and staff
                recipients = [incident.user_id, incident.assigned_crew_id, incident.assigned_supervisor_id]
            
            title = "New Comment Added"
            message = f"New comment on incident {incident.ticket_id}"
            
            # Send notifications (simplified)
            for recipient_id in recipients:
                if recipient_id:
                    send_fcm_notification(
                        token="",  # Would get from user service
                        title=title,
                        message=message,
                        data={
                            "incident_id": str(incident.id),
                            "ticket_id": incident.ticket_id,
                            "comment_id": str(comment.id)
                        }
                    )
            
        except Exception as e:
            logger.error(f"Failed to notify about comment: {e}")
    
    def _update_incident_analytics(self, ward_id: str) -> None:
        """Update incident analytics for a ward."""
        try:
            today = datetime.utcnow().date()
            
            # Get or create analytics record for today
            analytics = self.db.query(IncidentAnalytics).filter(
                and_(
                    IncidentAnalytics.ward_id == ward_id,
                    func.date(IncidentAnalytics.date) == today
                )
            ).first()
            
            if not analytics:
                analytics = IncidentAnalytics(
                    ward_id=ward_id,
                    date=today
                )
                self.db.add(analytics)
            
            # Update counts
            incidents = self.db.query(Incident).filter(Incident.ward_id == ward_id)
            
            analytics.total_incidents = incidents.count()
            analytics.open_incidents = incidents.filter(Incident.status == IncidentStatus.OPEN).count()
            analytics.resolved_incidents = incidents.filter(Incident.status == IncidentStatus.RESOLVED).count()
            analytics.escalated_incidents = incidents.filter(Incident.status == IncidentStatus.ESCALATED).count()
            
            # Category breakdown
            analytics.black_spot_count = incidents.filter(Incident.category == IncidentCategory.BLACK_SPOT).count()
            analytics.overflowing_bin_count = incidents.filter(Incident.category == IncidentCategory.OVERFLOWING_BIN).count()
            analytics.illegal_dumping_count = incidents.filter(Incident.category == IncidentCategory.ILLEGAL_DUMPING).count()
            
            # Average resolution time
            resolved_incidents = incidents.filter(Incident.status == IncidentStatus.RESOLVED, Incident.resolved_at.isnot(None))
            if resolved_incidents.count() > 0:
                total_resolution_time = 0
                for incident in resolved_incidents:
                    total_resolution_time += incident.resolution_time_hours or 0
                analytics.avg_resolution_time_hours = total_resolution_time / resolved_incidents.count()
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update incident analytics: {e}")


class WardService:
    """Ward management service."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_ward(self, ward_data: WardCreate) -> Ward:
        """Create new ward."""
        # Check if ward code already exists
        existing_ward = self.db.query(Ward).filter(Ward.code == ward_data.code).first()
        if existing_ward:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ward code already exists"
            )
        
        ward = Ward(
            name=ward_data.name,
            code=ward_data.code,
            boundary=ward_data.boundary,
            center_latitude=ward_data.center_latitude,
            center_longitude=ward_data.center_longitude,
            sla_hours=ward_data.sla_hours,
            supervisor_id=ward_data.supervisor_id
        )
        
        self.db.add(ward)
        self.db.commit()
        self.db.refresh(ward)
        
        return ward
    
    def get_ward_by_id(self, ward_id: str) -> Optional[Ward]:
        """Get ward by ID."""
        return self.db.query(Ward).filter(Ward.id == ward_id).first()
    
    def get_ward_by_code(self, code: str) -> Optional[Ward]:
        """Get ward by code."""
        return self.db.query(Ward).filter(Ward.code == code).first()
    
    def list_wards(self, active_only: bool = True) -> List[Ward]:
        """List all wards."""
        query = self.db.query(Ward)
        if active_only:
            query = query.filter(Ward.is_active == True)
        return query.order_by(Ward.name).all()
    
    def update_ward(self, ward_id: str, ward_data: WardCreate) -> Ward:
        """Update ward information."""
        ward = self.get_ward_by_id(ward_id)
        if not ward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ward not found"
            )
        
        # Update fields
        update_data = ward_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(ward, field, value)
        
        self.db.commit()
        self.db.refresh(ward)
        
        return ward
    
    def deactivate_ward(self, ward_id: str) -> bool:
        """Deactivate ward."""
        ward = self.get_ward_by_id(ward_id)
        if not ward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ward not found"
            )
        
        ward.is_active = False
        self.db.commit()
        
        return True
