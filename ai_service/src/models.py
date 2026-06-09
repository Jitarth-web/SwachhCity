"""
Data models for AI & Analytics Service.
IEEE Std 830-1998 SRS compliant data models.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text, Float, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from datetime import datetime
import uuid
from shared.models import WasteCategory

from .database import Base


class AIModel(Base):
    """
    AI model management for versioning and tracking.
    Stores model metadata and performance metrics.
    """
    __tablename__ = "ai_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False, comment="Model name")
    version = Column(String(20), nullable=False, comment="Model version")
    model_type = Column(String(50), nullable=False, comment="Model type (classification, optimization, prediction)")
    file_path = Column(String(500), nullable=False, comment="Model file path")
    
    # Performance metrics
    accuracy = Column(Float, nullable=True, comment="Model accuracy")
    precision = Column(Float, nullable=True, comment="Model precision")
    recall = Column(Float, nullable=True, comment="Model recall")
    f1_score = Column(Float, nullable=True, comment="F1 score")
    inference_time_ms = Column(Float, nullable=True, comment="Average inference time in milliseconds")
    
    # Training metadata
    training_data_size = Column(Integer, nullable=True, comment="Training dataset size")
    training_date = Column(DateTime(timezone=True), nullable=True, comment="Training completion date")
    training_parameters = Column(JSONB, nullable=True, comment="Training hyperparameters")
    
    # Deployment metadata
    is_active = Column(Boolean, default=False, nullable=False, comment="Currently deployed model")
    deployed_at = Column(DateTime(timezone=True), nullable=True, comment="Deployment timestamp")
    deployment_environment = Column(String(50), nullable=True, comment="Deployment environment")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Model creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")

    def __repr__(self):
        return f"<AIModel(id={self.id}, name={self.name}, version={self.version}, type={self.model_type})>"


class WasteClassification(Base):
    """
    Waste classification results from AI model.
    Stores classification outcomes with confidence scores.
    """
    __tablename__ = "waste_classifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    image_url = Column(String(500), nullable=False, comment="Original image URL")
    thumbnail_url = Column(String(500), nullable=True, comment="Thumbnail URL")
    
    # Classification results
    predicted_category = Column(Enum(WasteCategory), nullable=False, comment="Predicted waste category")
    confidence_score = Column(Float, nullable=False, comment="Classification confidence (0-1)")
    
    # Detailed probabilities for all categories
    category_probabilities = Column(JSONB, nullable=True, comment="Probabilities for all categories")
    
    # Processing metadata
    model_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="AI model used")
    processing_time_ms = Column(Integer, nullable=False, comment="Processing time in milliseconds")
    image_size_bytes = Column(Integer, nullable=True, comment="Image size in bytes")
    image_dimensions = Column(JSONB, nullable=True, comment="Image dimensions (width, height)")
    
    # Quality metrics
    image_quality_score = Column(Float, nullable=True, comment="Image quality assessment")
    blur_detected = Column(Boolean, default=False, nullable=False, comment="Blur detection result")
    lighting_quality = Column(String(20), nullable=True, comment="Lighting quality assessment")
    
    # Human verification
    verified_by_human = Column(Boolean, default=False, nullable=False, comment="Human verification status")
    human_verified_category = Column(Enum(WasteCategory), nullable=True, comment="Human-verified category")
    verification_confidence = Column(Float, nullable=True, comment="Human verification confidence")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Classification timestamp")
    verified_at = Column(DateTime(timezone=True), nullable=True, comment="Human verification timestamp")

    def __repr__(self):
        return f"<WasteClassification(id={self.id}, category={self.predicted_category}, confidence={self.confidence_score})>"


class RouteOptimization(Base):
    """
    Route optimization results and tracking.
    Stores optimization outcomes and performance metrics.
    """
    __tablename__ = "route_optimizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    optimization_request_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Request tracking ID")
    
    # Input parameters
    truck_locations = Column(JSONB, nullable=False, comment="Current truck locations")
    pickup_locations = Column(JSONB, nullable=False, comment="Pending pickup locations")
    optimization_parameters = Column(JSONB, nullable=True, comment="Optimization parameters")
    
    # Optimization results
    optimized_routes = Column(JSONB, nullable=False, comment="Optimized route assignments")
    total_distance_km = Column(Float, nullable=False, comment="Total optimized distance")
    estimated_time_minutes = Column(Integer, nullable=False, comment="Estimated completion time")
    
    # Performance metrics
    optimization_time_ms = Column(Integer, nullable=False, comment="Optimization processing time")
    distance_savings_km = Column(Float, nullable=True, comment="Distance saved compared to baseline")
    time_savings_minutes = Column(Integer, nullable=True, comment="Time saved compared to baseline")
    efficiency_improvement = Column(Float, nullable=True, comment="Efficiency improvement percentage")
    
    # Algorithm details
    algorithm_used = Column(String(50), nullable=False, comment="Optimization algorithm used")
    algorithm_parameters = Column(JSONB, nullable=True, comment="Algorithm-specific parameters")
    iterations = Column(Integer, nullable=True, comment="Optimization iterations")
    convergence_score = Column(Float, nullable=True, comment="Algorithm convergence score")
    
    # Status and metadata
    status = Column(String(20), default="completed", comment="Optimization status")
    error_message = Column(Text, nullable=True, comment="Error message if failed")
    applied_at = Column(DateTime(timezone=True), nullable=True, comment="When optimization was applied")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Optimization timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")

    def __repr__(self):
        return f"<RouteOptimization(id={self.id}, algorithm={self.algorithm_used}, status={self.status})>"


class PredictiveAnalytics(Base):
    """
    Predictive analytics results for hotspot detection.
    Stores predictions and model performance metrics.
    """
    __tablename__ = "predictive_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    analysis_type = Column(String(50), nullable=False, comment="Analysis type (hotspot, demand, etc.)")
    target_date = Column(DateTime(timezone=True), nullable=False, index=True, comment="Target prediction date")
    
    # Prediction data
    prediction_data = Column(JSONB, nullable=False, comment="Prediction results as GeoJSON")
    confidence_level = Column(Float, nullable=False, comment="Overall prediction confidence")
    prediction_horizon_days = Column(Integer, nullable=False, comment="Prediction horizon in days")
    
    # Model information
    model_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="AI model used")
    model_version = Column(String(20), nullable=True, comment="Model version")
    training_data_period = Column(JSONB, nullable=True, comment="Training data period")
    
    # Performance metrics
    historical_accuracy = Column(Float, nullable=True, comment="Historical accuracy of similar predictions")
    processing_time_ms = Column(Integer, nullable=False, comment="Processing time")
    
    # Input data metadata
    data_points_used = Column(Integer, nullable=True, comment="Number of data points used")
    data_quality_score = Column(Float, nullable=True, comment="Quality score of input data")
    outlier_count = Column(Integer, nullable=True, comment="Number of outliers detected")
    
    # Validation and feedback
    validated_at = Column(DateTime(timezone=True), nullable=True, comment="Prediction validation timestamp")
    actual_outcome = Column(JSONB, nullable=True, comment="Actual outcome for comparison")
    prediction_accuracy = Column(Float, nullable=True, comment="Actual prediction accuracy")
    
    # Status
    status = Column(String(20), default="active", comment="Prediction status")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Prediction creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")

    def __repr__(self):
        return f"<PredictiveAnalytics(id={self.id}, type={self.analysis_type}, target_date={self.target_date})>"


class AIProcessingLog(Base):
    """
    AI processing log for monitoring and debugging.
    Tracks all AI service operations and performance.
    """
    __tablename__ = "ai_processing_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    service_type = Column(String(50), nullable=False, comment="Service type (classification, optimization, prediction)")
    operation_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="Related operation ID")
    
    # Request details
    request_data = Column(JSONB, nullable=True, comment="Request data (sanitized)")
    request_size_bytes = Column(Integer, nullable=True, comment="Request size in bytes")
    
    # Processing details
    model_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="AI model used")
    processing_time_ms = Column(Integer, nullable=False, comment="Processing time in milliseconds")
    memory_usage_mb = Column(Float, nullable=True, comment="Memory usage in MB")
    cpu_usage_percent = Column(Float, nullable=True, comment="CPU usage percentage")
    
    # Results
    success = Column(Boolean, nullable=False, comment="Processing success status")
    result_data = Column(JSONB, nullable=True, comment="Result data (sanitized)")
    error_message = Column(Text, nullable=True, comment="Error message if failed")
    
    # Performance metrics
    cache_hit = Column(Boolean, default=False, nullable=False, comment="Cache hit status")
    queue_time_ms = Column(Integer, nullable=True, comment="Time spent in queue")
    
    # Client information
    client_ip = Column(String(45), nullable=True, comment="Client IP address")
    user_agent = Column(Text, nullable=True, comment="User agent string")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Processing timestamp")

    def __repr__(self):
        return f"<AIProcessingLog(id={self.id}, service={self.service_type}, success={self.success}, time_ms={self.processing_time_ms})>"


class ModelTraining(Base):
    """
    Model training tracking and metadata.
    Stores training runs and their outcomes.
    """
    __tablename__ = "model_training"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    model_type = Column(String(50), nullable=False, comment="Model type being trained")
    training_run_id = Column(String(100), unique=True, nullable=False, comment="Training run identifier")
    
    # Training configuration
    training_config = Column(JSONB, nullable=False, comment="Training configuration")
    hyperparameters = Column(JSONB, nullable=True, comment="Hyperparameters used")
    
    # Data information
    training_data_path = Column(String(500), nullable=True, comment="Training data path")
    validation_data_path = Column(String(500), nullable=True, comment="Validation data path")
    training_samples = Column(Integer, nullable=True, comment="Number of training samples")
    validation_samples = Column(Integer, nullable=True, comment="Number of validation samples")
    
    # Training metrics
    final_loss = Column(Float, nullable=True, comment="Final training loss")
    final_accuracy = Column(Float, nullable=True, comment="Final training accuracy")
    validation_loss = Column(Float, nullable=True, comment="Final validation loss")
    validation_accuracy = Column(Float, nullable=True, comment="Final validation accuracy")
    
    # Training process
    epochs_completed = Column(Integer, nullable=True, comment="Number of epochs completed")
    training_time_minutes = Column(Integer, nullable=True, comment="Total training time in minutes")
    early_stopped = Column(Boolean, default=False, nullable=False, comment="Early stopping triggered")
    
    # Resource usage
    gpu_hours = Column(Float, nullable=True, comment="GPU hours used")
    memory_peak_gb = Column(Float, nullable=True, comment="Peak memory usage in GB")
    
    # Status and results
    status = Column(String(20), default="running", comment="Training status")
    model_file_path = Column(String(500), nullable=True, comment="Trained model file path")
    error_message = Column(Text, nullable=True, comment="Error message if failed")
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Training start timestamp")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="Training completion timestamp")

    def __repr__(self):
        return f"<ModelTraining(id={self.id}, type={self.model_type}, status={self.status})>"


class AIModelCache(Base):
    """
    AI model caching for performance optimization.
    Stores cached results to avoid redundant processing.
    """
    __tablename__ = "ai_model_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    cache_key = Column(String(255), unique=True, nullable=False, index=True, comment="Cache key")
    service_type = Column(String(50), nullable=False, comment="Service type")
    
    # Cached data
    result_data = Column(JSONB, nullable=False, comment="Cached result data")
    confidence_score = Column(Float, nullable=True, comment="Result confidence")
    
    # Cache metadata
    model_id = Column(UUID(as_uuid=True), nullable=True, index=True, comment="AI model used")
    processing_time_ms = Column(Integer, nullable=True, comment="Original processing time")
    hit_count = Column(Integer, default=0, nullable=False, comment="Cache hit count")
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=False, comment="Cache expiration timestamp")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Cache creation timestamp")
    last_accessed = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Last access timestamp")

    def __repr__(self):
        return f"<AIModelCache(id={self.id}, key={self.cache_key}, service={self.service_type})>"
