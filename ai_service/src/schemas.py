"""
Pydantic schemas for AI & Analytics Service.
IEEE Std 830-1998 SRS compliant data validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field, validator
import uuid
from shared.models import WasteCategory


class WasteClassificationRequest(BaseModel):
    """Waste classification request schema."""
    image_url: str = Field(..., description="URL of image to classify")
    model_version: Optional[str] = Field("latest", description="Model version to use")
    include_probabilities: bool = Field(True, description="Include all category probabilities")
    quality_check: bool = Field(True, description="Perform image quality check")

    @validator('image_url')
    def validate_image_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Image URL must be a valid HTTP/HTTPS URL')
        return v


class WasteClassificationResponse(BaseModel):
    """Waste classification response schema."""
    id: uuid.UUID
    image_url: str
    predicted_category: WasteCategory
    confidence_score: float
    category_probabilities: Optional[Dict[str, float]]
    processing_time_ms: int
    model_id: uuid.UUID
    model_version: str
    image_quality_score: Optional[float]
    blur_detected: bool
    lighting_quality: Optional[str]
    verified_by_human: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RouteOptimizationRequest(BaseModel):
    """Route optimization request schema."""
    truck_locations: List[Dict[str, Any]] = Field(..., min_items=1, description="Current truck locations")
    pickup_locations: List[Dict[str, Any]] = Field(..., min_items=1, description="Pending pickup locations")
    optimization_parameters: Optional[Dict[str, Any]] = Field(None, description="Optimization parameters")
    algorithm: str = Field("hybrid", regex="^(astar|genetic|hybrid)$", description="Optimization algorithm")
    time_limit_seconds: int = Field(30, gt=0, le=300, description="Time limit for optimization")

    @validator('truck_locations')
    def validate_truck_locations(cls, v):
        for location in v:
            if not all(key in location for key in ['id', 'latitude', 'longitude']):
                raise ValueError('Each truck location must have id, latitude, and longitude')
            if not (-90 <= location['latitude'] <= 90):
                raise ValueError('Latitude must be between -90 and 90')
            if not (-180 <= location['longitude'] <= 180):
                raise ValueError('Longitude must be between -180 and 180')
        return v

    @validator('pickup_locations')
    def validate_pickup_locations(cls, v):
        for location in v:
            if not all(key in location for key in ['id', 'latitude', 'longitude']):
                raise ValueError('Each pickup location must have id, latitude, and longitude')
            if not (-90 <= location['latitude'] <= 90):
                raise ValueError('Latitude must be between -90 and 90')
            if not (-180 <= location['longitude'] <= 180):
                raise ValueError('Longitude must be between -180 and 180')
        return v


class RouteOptimizationResponse(BaseModel):
    """Route optimization response schema."""
    id: uuid.UUID
    optimization_request_id: uuid.UUID
    optimized_routes: Dict[str, List[Dict[str, Any]]]
    total_distance_km: float
    estimated_time_minutes: int
    distance_savings_km: Optional[float]
    time_savings_minutes: Optional[int]
    efficiency_improvement: Optional[float]
    algorithm_used: str
    processing_time_ms: int
    iterations: Optional[int]
    convergence_score: Optional[float]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PredictiveAnalyticsRequest(BaseModel):
    """Predictive analytics request schema."""
    analysis_type: str = Field(..., regex="^(hotspot|demand|capacity)$", description="Type of analysis")
    target_date: datetime = Field(..., description="Target prediction date")
    prediction_horizon_days: int = Field(30, gt=0, le=365, description="Prediction horizon in days")
    ward_ids: Optional[List[str]] = Field(None, description="Specific wards to analyze")
    model_version: Optional[str] = Field("latest", description="Model version to use")
    include_confidence: bool = Field(True, description="Include confidence levels")

    @validator('target_date')
    def validate_target_date(cls, v):
        if v <= datetime.utcnow():
            raise ValueError('Target date must be in the future')
        return v


class PredictiveAnalyticsResponse(BaseModel):
    """Predictive analytics response schema."""
    id: uuid.UUID
    analysis_type: str
    target_date: datetime
    prediction_data: Dict[str, Any]
    confidence_level: float
    prediction_horizon_days: int
    model_id: uuid.UUID
    model_version: str
    historical_accuracy: Optional[float]
    processing_time_ms: int
    data_points_used: Optional[int]
    data_quality_score: Optional[float]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AIModelInfo(BaseModel):
    """AI model information schema."""
    id: uuid.UUID
    name: str
    version: str
    model_type: str
    accuracy: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    f1_score: Optional[float]
    inference_time_ms: Optional[float]
    is_active: bool
    deployed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ModelTrainingRequest(BaseModel):
    """Model training request schema."""
    model_type: str = Field(..., regex="^(classification|optimization|prediction)$", description="Model type")
    training_config: Dict[str, Any] = Field(..., description="Training configuration")
    hyperparameters: Optional[Dict[str, Any]] = Field(None, description="Hyperparameters")
    training_data_path: Optional[str] = Field(None, description="Training data path")
    validation_split: float = Field(0.2, ge=0.1, le=0.5, description="Validation data split ratio")


class ModelTrainingResponse(BaseModel):
    """Model training response schema."""
    id: uuid.UUID
    training_run_id: str
    model_type: str
    status: str
    final_accuracy: Optional[float]
    validation_accuracy: Optional[float]
    epochs_completed: Optional[int]
    training_time_minutes: Optional[int]
    gpu_hours: Optional[float]
    memory_peak_gb: Optional[float]
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class AIProcessingLogResponse(BaseModel):
    """AI processing log response schema."""
    id: uuid.UUID
    service_type: str
    operation_id: Optional[uuid.UUID]
    processing_time_ms: int
    success: bool
    model_id: Optional[uuid.UUID]
    cache_hit: bool
    request_size_bytes: Optional[int]
    memory_usage_mb: Optional[float]
    cpu_usage_percent: Optional[float]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AIHealthCheck(BaseModel):
    """AI service health check schema."""
    status: str
    timestamp: datetime
    version: str
    models_loaded: Dict[str, bool]
    gpu_available: bool
    gpu_memory_gb: Optional[float]
    cpu_usage_percent: float
    memory_usage_mb: float
    cache_size: int
    queue_length: int


class AIMetricsResponse(BaseModel):
    """AI service metrics schema."""
    total_classifications_today: int
    total_optimizations_today: int
    total_predictions_today: int
    avg_processing_time_ms: float
    cache_hit_rate: float
    model_accuracy_rates: Dict[str, float]
    gpu_utilization_percent: float
    memory_utilization_percent: float
    active_models: int
    queue_length: int


class BatchClassificationRequest(BaseModel):
    """Batch waste classification request schema."""
    image_urls: List[str] = Field(..., min_items=1, max_items=50, description="List of image URLs")
    model_version: Optional[str] = Field("latest", description="Model version to use")
    include_probabilities: bool = Field(False, description="Include all category probabilities")
    quality_check: bool = Field(True, description="Perform image quality check")

    @validator('image_urls')
    def validate_image_urls(cls, v):
        for url in v:
            if not url.startswith(('http://', 'https://')):
                raise ValueError('All image URLs must be valid HTTP/HTTPS URLs')
        return v


class BatchClassificationResponse(BaseModel):
    """Batch classification response schema."""
    request_id: uuid.UUID
    results: List[WasteClassificationResponse]
    total_processed: int
    successful: int
    failed: int
    total_processing_time_ms: int
    avg_processing_time_ms: float
    created_at: datetime


class ModelComparisonRequest(BaseModel):
    """Model comparison request schema."""
    model_ids: List[uuid.UUID] = Field(..., min_items=2, max_items=5, description="Models to compare")
    test_data_path: Optional[str] = Field(None, description="Test dataset path")
    sample_size: int = Field(100, gt=0, le=10000, description="Sample size for comparison")


class ModelComparisonResponse(BaseModel):
    """Model comparison response schema."""
    comparison_id: uuid.UUID
    models: List[Dict[str, Any]]
    metrics: Dict[str, Dict[str, float]]
    winner: uuid.UUID
    comparison_date: datetime
    sample_size: int
    processing_time_ms: int


class APIResponse(BaseModel):
    """Standard API response schema."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CacheStatsResponse(BaseModel):
    """Cache statistics response schema."""
    total_entries: int
    hit_rate: float
    miss_rate: float
    memory_usage_mb: float
    oldest_entry: Optional[datetime]
    newest_entry: Optional[datetime]
    entries_by_service: Dict[str, int]


class ModelDeploymentRequest(BaseModel):
    """Model deployment request schema."""
    model_id: uuid.UUID
    deployment_environment: str = Field("production", regex="^(development|staging|production)$")
    rollout_percentage: float = Field(100.0, ge=0.0, le=100.0, description="Rollout percentage")
    canary_mode: bool = Field(False, description="Enable canary deployment mode")


class ModelDeploymentResponse(BaseModel):
    """Model deployment response schema."""
    deployment_id: uuid.UUID
    model_id: uuid.UUID
    deployment_environment: str
    rollout_percentage: float
    canary_mode: bool
    status: str
    deployed_at: datetime
    previous_model_id: Optional[uuid.UUID]
