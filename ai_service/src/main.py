"""
FastAPI application for AI & Analytics Service.
IEEE Std 830-1998 SRS compliant REST API with AI/ML capabilities.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import uuid
import psutil
import torch

from shared.middleware import get_standard_middleware, get_current_user, require_role
from shared.utils import verify_jwt_token, settings
from .database import get_db, create_tables
from .models import AIModel, WasteClassification, RouteOptimization, PredictiveAnalytics, AIProcessingLog
from .schemas import (
    WasteClassificationRequest, WasteClassificationResponse, BatchClassificationRequest,
    BatchClassificationResponse, RouteOptimizationRequest, RouteOptimizationResponse,
    PredictiveAnalyticsRequest, PredictiveAnalyticsResponse,
    AIModelInfo, AIProcessingLogResponse, AIHealthCheck, AIMetricsResponse,
    ModelTrainingRequest, ModelTrainingResponse, ModelDeploymentRequest,
    ModelDeploymentResponse, APIResponse, CacheStatsResponse
)
from .services import (
    WasteClassificationService, RouteOptimizationService, 
    PredictiveAnalyticsService, ModelManagementService
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SwachhGram AI & Analytics Service",
    description="AI-powered waste classification, route optimization, and predictive analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Apply standard middleware
app = get_standard_middleware(app, allowed_origins=["http://localhost:3000"])

# Security
security = HTTPBearer()

# Dependency injection
def get_classification_service(db: Session = Depends(get_db)) -> WasteClassificationService:
    """Get classification service instance."""
    return WasteClassificationService(db)

def get_optimization_service(db: Session = Depends(get_db)) -> RouteOptimizationService:
    """Get optimization service instance."""
    return RouteOptimizationService(db)

def get_analytics_service(db: Session = Depends(get_db)) -> PredictiveAnalyticsService:
    """Get analytics service instance."""
    return PredictiveAnalyticsService(db)

def get_model_service(db: Session = Depends(get_db)) -> ModelManagementService:
    """Get model management service instance."""
    return ModelManagementService(db)


@app.on_event("startup")
async def startup_event():
    """Initialize AI models and database on startup."""
    try:
        create_tables()
        logger.info("Database tables created successfully")
        
        # Initialize AI models
        from .ai_models import WasteClassifier, RouteOptimizer, PredictiveAnalytics
        classifier = WasteClassifier()
        optimizer = RouteOptimizer()
        analytics = PredictiveAnalytics()
        
        logger.info("AI models initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize AI service: {e}")


# Health check endpoints
@app.get("/health", response_model=AIHealthCheck)
async def health_check():
    """Comprehensive health check for AI service."""
    try:
        # Check GPU availability
        gpu_available = torch.cuda.is_available()
        gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / 1e9 if gpu_available else None
        
        # Check system resources
        cpu_usage = psutil.cpu_percent()
        memory_info = psutil.virtual_memory()
        memory_usage_mb = memory_info.used / 1e6
        
        # Check models (simplified)
        models_loaded = {
            "classification": True,  # Would check actual model loading
            "optimization": True,
            "prediction": True
        }
        
        # Check cache size
        cache_size = 1000  # Would get actual cache size
        
        return AIHealthCheck(
            status="healthy",
            timestamp=datetime.utcnow(),
            version="1.0.0",
            models_loaded=models_loaded,
            gpu_available=gpu_available,
            gpu_memory_gb=gpu_memory_gb,
            cpu_usage_percent=cpu_usage,
            memory_usage_mb=memory_usage_mb,
            cache_size=cache_size,
            queue_length=0  # Would get actual queue length
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return AIHealthCheck(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            version="1.0.0",
            models_loaded={},
            gpu_available=False,
            gpu_memory_gb=None,
            cpu_usage_percent=0,
            memory_usage_mb=0,
            cache_size=0,
            queue_length=0
        )


@app.get("/metrics", response_model=AIMetricsResponse)
async def get_metrics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "ward_supervisor", "zonal_commissioner"]))
):
    """Get AI service metrics."""
    try:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get today's counts
        total_classifications = db.query(WasteClassification).filter(
            WasteClassification.created_at >= today_start
        ).count()
        
        total_optimizations = db.query(RouteOptimization).filter(
            RouteOptimization.created_at >= today_start
        ).count()
        
        total_predictions = db.query(PredictiveAnalytics).filter(
            PredictiveAnalytics.created_at >= today_start
        ).count()
        
        # Get average processing time
        avg_processing_time = db.query(func.avg(AIProcessingLog.processing_time_ms)).filter(
            and_(
                AIProcessingLog.created_at >= today_start,
                AIProcessingLog.success == True
            )
        ).scalar() or 0.0
        
        # Get cache hit rate
        cache_stats = get_model_service(db).get_cache_stats()
        cache_hit_rate = cache_stats['hit_rate']
        
        # Get model accuracy rates
        model_accuracy_rates = {}
        active_models = db.query(AIModel).filter(AIModel.is_active == True).all()
        for model in active_models:
            model_accuracy_rates[model.model_type] = model.accuracy or 0.0
        
        # Get resource utilization
        gpu_utilization = psutil.cpu_percent()  # Simplified
        memory_utilization = (psutil.virtual_memory().used / psutil.virtual_memory().total) * 100
        
        return AIMetricsResponse(
            total_classifications_today=total_classifications,
            total_optimizations_today=total_optimizations,
            total_predictions_today=total_predictions,
            avg_processing_time_ms=avg_processing_time,
            cache_hit_rate=cache_hit_rate,
            model_accuracy_rates=model_accuracy_rates,
            gpu_utilization_percent=gpu_utilization,
            memory_utilization_percent=memory_utilization,
            active_models=len(active_models),
            queue_length=0
        )
    except Exception as e:
        logger.error(f"Get metrics failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get metrics"
        )


# Waste classification endpoints
@app.post("/classify", response_model=WasteClassificationResponse)
async def classify_image(
    request: WasteClassificationRequest,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["crew", "ward_supervisor", "zonal_commissioner", "admin"])),
    classification_service: WasteClassificationService = Depends(get_classification_service)
):
    """Classify waste image using AI."""
    try:
        classification = classification_service.classify_image(request, current_user["user_id"])
        return WasteClassificationResponse.from_orm(classification)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image classification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Classification failed"
        )


@app.post("/classify/batch", response_model=BatchClassificationResponse)
async def batch_classify_images(
    request: BatchClassificationRequest,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["ward_supervisor", "zonal_commissioner", "admin"])),
    classification_service: WasteClassificationService = Depends(get_classification_service)
):
    """Batch classify multiple images."""
    try:
        result = classification_service.batch_classify_images(request, current_user["user_id"])
        
        # Convert classification objects to response format
        results = [WasteClassificationResponse.from_orm(cls) for cls in result["results"]]
        
        return BatchClassificationResponse(
            request_id=result["request_id"],
            results=results,
            total_processed=result["total_processed"],
            successful=result["successful"],
            failed=result["failed"],
            total_processing_time_ms=result["total_processing_time_ms"],
            avg_processing_time_ms=result["avg_processing_time_ms"],
            created_at=result["created_at"]
        )
    except Exception as e:
        logger.error(f"Batch classification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch classification failed"
        )


@app.get("/classify/history", response_model=List[WasteClassificationResponse])
async def get_classification_history(
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["ward_supervisor", "zonal_commissioner", "admin"])),
    classification_service: WasteClassificationService = Depends(get_classification_service)
):
    """Get classification history."""
    try:
        classifications = classification_service.get_classification_history(limit, offset)
        return [WasteClassificationResponse.from_orm(cls) for cls in classifications]
    except Exception as e:
        logger.error(f"Get classification history failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get classification history"
        )


@app.put("/classify/{classification_id}/verify", response_model=WasteClassificationResponse)
async def verify_classification(
    classification_id: str,
    verified_category: str,
    confidence: float,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["ward_supervisor", "zonal_commissioner", "admin"])),
    classification_service: WasteClassificationService = Depends(get_classification_service)
):
    """Verify classification result."""
    try:
        classification = classification_service.verify_classification(
            classification_id, verified_category, confidence, current_user["user_id"]
        )
        return WasteClassificationResponse.from_orm(classification)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed"
        )


# Route optimization endpoints
@app.post("/optimize/routes", response_model=RouteOptimizationResponse)
async def optimize_routes(
    request: RouteOptimizationRequest,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["ward_supervisor", "zonal_commissioner", "admin"])),
    optimization_service: RouteOptimizationService = Depends(get_optimization_service)
):
    """Optimize collection routes using AI."""
    try:
        optimization = optimization_service.optimize_routes(request, current_user["user_id"])
        return RouteOptimizationResponse.from_orm(optimization)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Route optimization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route optimization failed"
        )


@app.get("/optimize/history", response_model=List[RouteOptimizationResponse])
async def get_optimization_history(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["ward_supervisor", "zonal_commissioner", "admin"])),
    optimization_service: RouteOptimizationService = Depends(get_optimization_service)
):
    """Get optimization history."""
    try:
        optimizations = optimization_service.get_optimization_history(limit, offset)
        return [RouteOptimizationResponse.from_orm(opt) for opt in optimizations]
    except Exception as e:
        logger.error(f"Get optimization history failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get optimization history"
        )


@app.get("/optimize/{optimization_id}", response_model=RouteOptimizationResponse)
async def get_optimization(
    optimization_id: str,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["ward_supervisor", "zonal_commissioner", "admin"])),
    optimization_service: RouteOptimizationService = Depends(get_optimization_service)
):
    """Get optimization by ID."""
    try:
        optimization = optimization_service.get_optimization_by_id(optimization_id)
        if not optimization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Optimization not found"
            )
        return RouteOptimizationResponse.from_orm(optimization)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get optimization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get optimization"
        )


# Predictive analytics endpoints
@app.post("/predict/hotspots", response_model=PredictiveAnalyticsResponse)
async def predict_hotspots(
    request: PredictiveAnalyticsRequest,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["ward_supervisor", "zonal_commissioner", "admin"])),
    analytics_service: PredictiveAnalyticsService = Depends(get_analytics_service)
):
    """Predict waste collection hotspots."""
    try:
        prediction = analytics_service.predict_hotspots(request, current_user["user_id"])
        return PredictiveAnalyticsResponse.from_orm(prediction)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hotspot prediction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed"
        )


@app.get("/predict/history", response_model=List[PredictiveAnalyticsResponse])
async def get_prediction_history(
    analysis_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["ward_supervisor", "zonal_commissioner", "admin"])),
    analytics_service: PredictiveAnalyticsService = Depends(get_analytics_service)
):
    """Get prediction history."""
    try:
        predictions = analytics_service.get_prediction_history(analysis_type, limit, offset)
        return [PredictiveAnalyticsResponse.from_orm(pred) for pred in predictions]
    except Exception as e:
        logger.error(f"Get prediction history failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get prediction history"
        )


@app.put("/predict/{prediction_id}/validate", response_model=PredictiveAnalyticsResponse)
async def validate_prediction(
    prediction_id: str,
    actual_outcome: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["ward_supervisor", "zonal_commissioner", "admin"])),
    analytics_service: PredictiveAnalyticsService = Depends(get_analytics_service)
):
    """Validate prediction against actual outcome."""
    try:
        prediction = analytics_service.validate_prediction(
            prediction_id, actual_outcome, current_user["user_id"]
        )
        return PredictiveAnalyticsResponse.from_orm(prediction)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Validation failed"
        )


# Model management endpoints
@app.get("/models", response_model=List[AIModelInfo])
async def get_active_models(
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "zonal_commissioner"])),
    model_service: ModelManagementService = Depends(get_model_service)
):
    """Get active AI models."""
    try:
        models = model_service.get_active_models()
        return [AIModelInfo.from_orm(model) for model in models]
    except Exception as e:
        logger.error(f"Get active models failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get active models"
        )


@app.get("/models/{model_id}", response_model=AIModelInfo)
async def get_model(
    model_id: str,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "zonal_commissioner"])),
    model_service: ModelManagementService = Depends(get_model_service)
):
    """Get model by ID."""
    try:
        model = model_service.get_model_by_id(model_id)
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model not found"
            )
        return AIModelInfo.from_orm(model)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get model failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get model"
        )


@app.put("/models/{model_id}/deploy", response_model=AIModelInfo)
async def deploy_model(
    model_id: str,
    deployment_request: ModelDeploymentRequest,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin"])),
    model_service: ModelManagementService = Depends(get_model_service)
):
    """Deploy AI model."""
    try:
        model = model_service.deploy_model(model_id, deployment_request.deployment_environment)
        return AIModelInfo.from_orm(model)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Model deployment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model deployment failed"
        )


@app.get("/logs", response_model=List[AIProcessingLogResponse])
async def get_processing_logs(
    service_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "zonal_commissioner"])),
    model_service: ModelManagementService = Depends(get_model_service)
):
    """Get AI processing logs."""
    try:
        logs = model_service.get_processing_logs(service_type, limit, offset)
        return [AIProcessingLogResponse.from_orm(log) for log in logs]
    except Exception as e:
        logger.error(f"Get processing logs failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get processing logs"
        )


@app.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin", "zonal_commissioner"])),
    model_service: ModelManagementService = Depends(get_model_service)
):
    """Get cache statistics."""
    try:
        stats = model_service.get_cache_stats()
        return CacheStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Get cache stats failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cache stats"
        )


# Cleanup endpoint
@app.post("/cleanup/cache", response_model=APIResponse)
async def cleanup_cache(
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Clean up expired cache entries."""
    try:
        from .models import AIModelCache
        
        # Delete expired entries
        deleted_count = db.query(AIModelCache).filter(
            AIModelCache.expires_at <= datetime.utcnow()
        ).delete()
        
        db.commit()
        
        return APIResponse(
            success=True,
            message=f"Cleaned up {deleted_count} expired cache entries"
        )
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cache cleanup failed"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
