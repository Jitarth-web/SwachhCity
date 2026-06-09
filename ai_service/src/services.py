"""
Business logic services for AI & Analytics Service.
IEEE Std 830-1998 SRS compliant service layer.
"""

import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from fastapi import HTTPException, status
import logging
import redis
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import asyncio

from shared.utils import settings, verify_jwt_token
from .models import (
    AIModel, WasteClassification, RouteOptimization, PredictiveAnalytics,
    AIProcessingLog, AIModelCache, ModelTraining
)
from .schemas import (
    WasteClassificationRequest, RouteOptimizationRequest, PredictiveAnalyticsRequest,
    BatchClassificationRequest, ModelTrainingRequest
)
from .ai_models import WasteClassifier, RouteOptimizer, PredictiveAnalytics as AIAnalytics

logger = logging.getLogger(__name__)

# Redis client for caching
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


class WasteClassificationService:
    """Waste classification service with AI model integration."""
    
    def __init__(self, db: Session):
        self.db = db
        self.classifier = WasteClassifier()
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def classify_image(self, request: WasteClassificationRequest, user_id: str) -> WasteClassification:
        """Classify waste image with AI model."""
        start_time = time.time()
        processing_log_id = None
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(request.image_url, request.model_version)
            cached_result = self._get_cached_result(cache_key)
            
            if cached_result:
                logger.info(f"Cache hit for image classification: {request.image_url}")
                return self._create_classification_from_cache(cached_result, user_id)
            
            # Create processing log
            processing_log_id = self._create_processing_log(
                service_type="classification",
                request_data={"image_url": request.image_url, "model_version": request.model_version}
            )
            
            # Perform classification with timeout
            future = self.executor.submit(self.classifier.classify_image, request.image_url, request.include_probabilities)
            
            try:
                result = future.result(timeout=5)  # 5-second timeout
            except TimeoutError:
                logger.warning(f"Classification timeout for {request.image_url}")
                result = self._get_fallback_classification()
            
            # Create classification record
            classification = WasteClassification(
                image_url=request.image_url,
                predicted_category=result['predicted_category'],
                confidence_score=result['confidence_score'],
                category_probabilities=result.get('category_probabilities'),
                model_id=self._get_active_model_id("classification"),
                processing_time_ms=result['processing_time_ms'],
                image_quality_score=result.get('image_quality_score'),
                blur_detected=result.get('blur_detected', False),
                lighting_quality=result.get('lighting_quality')
            )
            
            self.db.add(classification)
            self.db.commit()
            self.db.refresh(classification)
            
            # Cache result
            self._cache_result(cache_key, result, expires_hours=24)
            
            # Update processing log
            if processing_log_id:
                self._update_processing_log(processing_log_id, True, result)
            
            logger.info(f"Classification completed: {classification.predicted_category} with confidence {classification.confidence_score}")
            return classification
            
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            if processing_log_id:
                self._update_processing_log(processing_log_id, False, None, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Classification failed"
            )
    
    def batch_classify_images(self, request: BatchClassificationRequest, user_id: str) -> Dict[str, Any]:
        """Batch classify multiple images."""
        start_time = time.time()
        results = []
        successful = 0
        failed = 0
        
        # Create processing log for batch operation
        batch_id = str(uuid.uuid4())
        processing_log_id = self._create_processing_log(
            service_type="batch_classification",
            request_data={"batch_id": batch_id, "image_count": len(request.image_urls)}
        )
        
        try:
            # Process images in parallel
            futures = []
            for image_url in request.image_urls:
                individual_request = WasteClassificationRequest(
                    image_url=image_url,
                    model_version=request.model_version,
                    include_probabilities=request.include_probabilities,
                    quality_check=request.quality_check
                )
                future = self.executor.submit(self.classify_image, individual_request, user_id)
                futures.append((image_url, future))
            
            # Collect results
            for image_url, future in futures:
                try:
                    result = future.result(timeout=5)
                    results.append(result)
                    successful += 1
                except Exception as e:
                    logger.error(f"Batch classification failed for {image_url}: {e}")
                    failed += 1
            
            total_processing_time = int((time.time() - start_time) * 1000)
            avg_processing_time = total_processing_time / len(request.image_urls) if request.image_urls else 0
            
            # Update processing log
            if processing_log_id:
                self._update_processing_log(processing_log_id, True, {
                    "successful": successful,
                    "failed": failed,
                    "total_processing_time_ms": total_processing_time
                })
            
            return {
                "request_id": batch_id,
                "results": results,
                "total_processed": len(request.image_urls),
                "successful": successful,
                "failed": failed,
                "total_processing_time_ms": total_processing_time,
                "avg_processing_time_ms": avg_processing_time,
                "created_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Batch classification failed: {e}")
            if processing_log_id:
                self._update_processing_log(processing_log_id, False, None, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Batch classification failed"
            )
    
    def get_classification_history(self, limit: int = 100, offset: int = 0) -> List[WasteClassification]:
        """Get classification history."""
        return self.db.query(WasteClassification).order_by(
            desc(WasteClassification.created_at)
        ).offset(offset).limit(limit).all()
    
    def verify_classification(self, classification_id: str, verified_category: str, 
                           confidence: float, user_id: str) -> WasteClassification:
        """Human verification of classification."""
        classification = self.db.query(WasteClassification).filter(
            WasteClassification.id == classification_id
        ).first()
        
        if not classification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Classification not found"
            )
        
        from shared.models import WasteCategory
        try:
            classification.human_verified_category = WasteCategory(verified_category)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid waste category"
            )
        
        classification.verified_by_human = True
        classification.verification_confidence = confidence
        classification.verified_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(classification)
        
        logger.info(f"Classification {classification_id} verified by human: {verified_category}")
        return classification
    
    def _generate_cache_key(self, image_url: str, model_version: str) -> str:
        """Generate cache key for classification result."""
        key_data = f"{image_url}:{model_version}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached classification result."""
        try:
            cached = self.db.query(AIModelCache).filter(
                and_(
                    AIModelCache.cache_key == cache_key,
                    AIModelCache.expires_at > datetime.utcnow()
                )
            ).first()
            
            if cached:
                # Update access statistics
                cached.hit_count += 1
                cached.last_accessed = datetime.utcnow()
                self.db.commit()
                return json.loads(cached.result_data)
            
            return None
        except Exception as e:
            logger.error(f"Cache retrieval failed: {e}")
            return None
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any], expires_hours: int = 24) -> None:
        """Cache classification result."""
        try:
            expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
            
            cache_entry = AIModelCache(
                cache_key=cache_key,
                service_type="classification",
                result_data=json.dumps(result),
                confidence_score=result.get('confidence_score', 0.0),
                model_id=self._get_active_model_id("classification"),
                processing_time_ms=result.get('processing_time_ms', 0),
                expires_at=expires_at
            )
            
            self.db.add(cache_entry)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Cache storage failed: {e}")
    
    def _create_classification_from_cache(self, cached_result: Dict[str, Any], user_id: str) -> WasteClassification:
        """Create classification record from cached result."""
        classification = WasteClassification(
            image_url="",  # Will be filled by caller
            predicted_category=cached_result['predicted_category'],
            confidence_score=cached_result['confidence_score'],
            category_probabilities=cached_result.get('category_probabilities'),
            model_id=self._get_active_model_id("classification"),
            processing_time_ms=cached_result['processing_time_ms'],
            image_quality_score=cached_result.get('image_quality_score'),
            blur_detected=cached_result.get('blur_detected', False),
            lighting_quality=cached_result.get('lighting_quality')
        )
        
        return classification
    
    def _get_active_model_id(self, model_type: str) -> Optional[uuid.UUID]:
        """Get active model ID for given type."""
        model = self.db.query(AIModel).filter(
            and_(AIModel.model_type == model_type, AIModel.is_active == True)
        ).first()
        return model.id if model else None
    
    def _create_processing_log(self, service_type: str, request_data: Dict[str, Any]) -> Optional[str]:
        """Create AI processing log entry."""
        try:
            log = AIProcessingLog(
                service_type=service_type,
                request_data=json.dumps(request_data),
                success=False  # Will be updated on completion
            )
            self.db.add(log)
            self.db.commit()
            return str(log.id)
        except Exception as e:
            logger.error(f"Failed to create processing log: {e}")
            return None
    
    def _update_processing_log(self, log_id: str, success: bool, result_data: Optional[Dict[str, Any]], 
                              error_message: Optional[str] = None) -> None:
        """Update AI processing log."""
        try:
            log = self.db.query(AIProcessingLog).filter(AIProcessingLog.id == log_id).first()
            if log:
                log.success = success
                log.result_data = json.dumps(result_data) if result_data else None
                log.error_message = error_message
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update processing log: {e}")
    
    def _get_fallback_classification(self) -> Dict[str, Any]:
        """Get fallback classification result."""
        from shared.models import WasteCategory
        return {
            'predicted_category': WasteCategory.MIXED,
            'confidence_score': 0.5,
            'category_probabilities': {
                WasteCategory.PLASTIC.value: 0.25,
                WasteCategory.ORGANIC.value: 0.25,
                WasteCategory.HAZARDOUS.value: 0.25,
                WasteCategory.MIXED.value: 0.25
            },
            'processing_time_ms': 100,
            'image_quality_score': 50.0,
            'blur_detected': False,
            'lighting_quality': 'unknown',
            'fallback': True
        }


class RouteOptimizationService:
    """Route optimization service with AI algorithms."""
    
    def __init__(self, db: Session):
        self.db = db
        self.optimizer = RouteOptimizer()
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    def optimize_routes(self, request: RouteOptimizationRequest, user_id: str) -> RouteOptimization:
        """Optimize collection routes using AI algorithms."""
        start_time = time.time()
        processing_log_id = None
        request_id = str(uuid.uuid4())
        
        try:
            # Create processing log
            processing_log_id = self._create_processing_log(
                service_type="optimization",
                request_data={
                    "request_id": request_id,
                    "truck_count": len(request.truck_locations),
                    "pickup_count": len(request.pickup_locations),
                    "algorithm": request.algorithm
                }
            )
            
            # Perform optimization with timeout
            future = self.executor.submit(self.optimizer.optimize_routes, request)
            
            try:
                result = future.result(timeout=request.time_limit_seconds)
            except TimeoutError:
                logger.warning(f"Route optimization timeout for request {request_id}")
                result = self.optimizer._fallback_optimization(request, start_time)
            
            # Create optimization record
            optimization = RouteOptimization(
                optimization_request_id=request_id,
                truck_locations=request.truck_locations,
                pickup_locations=request.pickup_locations,
                optimization_parameters=request.optimization_parameters,
                optimized_routes=result['optimized_routes'],
                total_distance_km=result['total_distance_km'],
                estimated_time_minutes=result['estimated_time_minutes'],
                distance_savings_km=result.get('distance_savings_km'),
                time_savings_minutes=result.get('time_savings_minutes'),
                efficiency_improvement=result.get('efficiency_improvement'),
                algorithm_used=result['algorithm_used'],
                optimization_time_ms=result['processing_time_ms'],
                iterations=result.get('iterations'),
                convergence_score=result.get('convergence_score'),
                status="completed"
            )
            
            self.db.add(optimization)
            self.db.commit()
            self.db.refresh(optimization)
            
            # Update processing log
            if processing_log_id:
                self._update_processing_log(processing_log_id, True, result)
            
            logger.info(f"Route optimization completed: {result['algorithm_used']} algorithm, {result['total_distance_km']}km total")
            return optimization
            
        except Exception as e:
            logger.error(f"Route optimization failed: {e}")
            if processing_log_id:
                self._update_processing_log(processing_log_id, False, None, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Route optimization failed"
            )
    
    def get_optimization_history(self, limit: int = 50, offset: int = 0) -> List[RouteOptimization]:
        """Get optimization history."""
        return self.db.query(RouteOptimization).order_by(
            desc(RouteOptimization.created_at)
        ).offset(offset).limit(limit).all()
    
    def get_optimization_by_id(self, optimization_id: str) -> Optional[RouteOptimization]:
        """Get optimization by ID."""
        return self.db.query(RouteOptimization).filter(
            RouteOptimization.id == optimization_id
        ).first()
    
    def _create_processing_log(self, service_type: str, request_data: Dict[str, Any]) -> Optional[str]:
        """Create AI processing log entry."""
        try:
            log = AIProcessingLog(
                service_type=service_type,
                request_data=json.dumps(request_data),
                success=False
            )
            self.db.add(log)
            self.db.commit()
            return str(log.id)
        except Exception as e:
            logger.error(f"Failed to create processing log: {e}")
            return None
    
    def _update_processing_log(self, log_id: str, success: bool, result_data: Optional[Dict[str, Any]], 
                              error_message: Optional[str] = None) -> None:
        """Update AI processing log."""
        try:
            log = self.db.query(AIProcessingLog).filter(AIProcessingLog.id == log_id).first()
            if log:
                log.success = success
                log.result_data = json.dumps(result_data) if result_data else None
                log.error_message = error_message
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update processing log: {e}")


class PredictiveAnalyticsService:
    """Predictive analytics service for hotspot detection."""
    
    def __init__(self, db: Session):
        self.db = db
        self.analytics = AIAnalytics()
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    def predict_hotspots(self, request: PredictiveAnalyticsRequest, user_id: str) -> PredictiveAnalytics:
        """Predict waste collection hotspots."""
        start_time = time.time()
        processing_log_id = None
        
        try:
            # Create processing log
            processing_log_id = self._create_processing_log(
                service_type="prediction",
                request_data={
                    "analysis_type": request.analysis_type,
                    "target_date": request.target_date.isoformat(),
                    "prediction_horizon_days": request.prediction_horizon_days
                }
            )
            
            # Perform prediction with timeout
            future = self.executor.submit(
                self.analytics.predict_hotspots,
                request.target_date,
                request.prediction_horizon_days,
                request.ward_ids
            )
            
            try:
                result = future.result(timeout=10)  # 10-second timeout
            except TimeoutError:
                logger.warning(f"Predictive analytics timeout for {request.analysis_type}")
                result = self.analytics._fallback_prediction(request.target_date, start_time)
            
            # Create analytics record
            analytics = PredictiveAnalytics(
                analysis_type=request.analysis_type,
                target_date=request.target_date,
                prediction_data=result['prediction_data'],
                confidence_level=result['confidence_level'],
                prediction_horizon_days=result['prediction_horizon_days'],
                model_id=self._get_active_model_id("prediction"),
                historical_accuracy=result.get('historical_accuracy'),
                processing_time_ms=result['processing_time_ms'],
                data_points_used=result.get('data_points_used'),
                data_quality_score=result.get('data_quality_score'),
                status="active"
            )
            
            self.db.add(analytics)
            self.db.commit()
            self.db.refresh(analytics)
            
            # Update processing log
            if processing_log_id:
                self._update_processing_log(processing_log_id, True, result)
            
            logger.info(f"Predictive analytics completed: {request.analysis_type} for {request.target_date}")
            return analytics
            
        except Exception as e:
            logger.error(f"Predictive analytics failed: {e}")
            if processing_log_id:
                self._update_processing_log(processing_log_id, False, None, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Predictive analytics failed"
            )
    
    def get_prediction_history(self, analysis_type: Optional[str] = None, 
                              limit: int = 50, offset: int = 0) -> List[PredictiveAnalytics]:
        """Get prediction history."""
        query = self.db.query(PredictiveAnalytics)
        
        if analysis_type:
            query = query.filter(PredictiveAnalytics.analysis_type == analysis_type)
        
        return query.order_by(desc(PredictiveAnalytics.created_at)).offset(offset).limit(limit).all()
    
    def validate_prediction(self, prediction_id: str, actual_outcome: Dict[str, Any], 
                           user_id: str) -> PredictiveAnalytics:
        """Validate prediction against actual outcome."""
        prediction = self.db.query(PredictiveAnalytics).filter(
            PredictiveAnalytics.id == prediction_id
        ).first()
        
        if not prediction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prediction not found"
            )
        
        prediction.actual_outcome = actual_outcome
        prediction.validated_at = datetime.utcnow()
        
        # Calculate prediction accuracy (simplified)
        prediction_accuracy = self._calculate_prediction_accuracy(
            prediction.prediction_data, actual_outcome
        )
        prediction.prediction_accuracy = prediction_accuracy
        
        self.db.commit()
        self.db.refresh(prediction)
        
        logger.info(f"Prediction {prediction_id} validated with accuracy {prediction_accuracy}")
        return prediction
    
    def _get_active_model_id(self, model_type: str) -> Optional[uuid.UUID]:
        """Get active model ID for given type."""
        model = self.db.query(AIModel).filter(
            and_(AIModel.model_type == model_type, AIModel.is_active == True)
        ).first()
        return model.id if model else None
    
    def _create_processing_log(self, service_type: str, request_data: Dict[str, Any]) -> Optional[str]:
        """Create AI processing log entry."""
        try:
            log = AIProcessingLog(
                service_type=service_type,
                request_data=json.dumps(request_data),
                success=False
            )
            self.db.add(log)
            self.db.commit()
            return str(log.id)
        except Exception as e:
            logger.error(f"Failed to create processing log: {e}")
            return None
    
    def _update_processing_log(self, log_id: str, success: bool, result_data: Optional[Dict[str, Any]], 
                              error_message: Optional[str] = None) -> None:
        """Update AI processing log."""
        try:
            log = self.db.query(AIProcessingLog).filter(AIProcessingLog.id == log_id).first()
            if log:
                log.success = success
                log.result_data = json.dumps(result_data) if result_data else None
                log.error_message = error_message
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update processing log: {e}")
    
    def _calculate_prediction_accuracy(self, prediction_data: Dict[str, Any], 
                                     actual_outcome: Dict[str, Any]) -> float:
        """Calculate prediction accuracy (simplified)."""
        # This is a simplified accuracy calculation
        # In production, this would use more sophisticated metrics
        try:
            predicted_features = prediction_data.get('features', [])
            actual_features = actual_outcome.get('features', [])
            
            if not predicted_features or not actual_features:
                return 0.5  # Default accuracy
            
            # Simple comparison based on feature count
            accuracy = min(1.0, len(predicted_features) / max(1, len(actual_features)))
            return accuracy
        except Exception as e:
            logger.error(f"Accuracy calculation failed: {e}")
            return 0.5


class ModelManagementService:
    """AI model management service."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_active_models(self) -> List[AIModel]:
        """Get all active AI models."""
        return self.db.query(AIModel).filter(AIModel.is_active == True).all()
    
    def get_model_by_id(self, model_id: str) -> Optional[AIModel]:
        """Get model by ID."""
        return self.db.query(AIModel).filter(AIModel.id == model_id).first()
    
    def deploy_model(self, model_id: str, environment: str = "production") -> AIModel:
        """Deploy AI model to specified environment."""
        model = self.get_model_by_id(model_id)
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model not found"
            )
        
        # Deactivate other models of same type
        self.db.query(AIModel).filter(
            and_(AIModel.model_type == model.model_type, AIModel.is_active == True)
        ).update({"is_active": False})
        
        # Activate this model
        model.is_active = True
        model.deployed_at = datetime.utcnow()
        model.deployment_environment = environment
        
        self.db.commit()
        self.db.refresh(model)
        
        logger.info(f"Model {model.name} v{model.version} deployed to {environment}")
        return model
    
    def get_processing_logs(self, service_type: Optional[str] = None, 
                          limit: int = 100, offset: int = 0) -> List[AIProcessingLog]:
        """Get AI processing logs."""
        query = self.db.query(AIProcessingLog)
        
        if service_type:
            query = query.filter(AIProcessingLog.service_type == service_type)
        
        return query.order_by(desc(AIProcessingLog.created_at)).offset(offset).limit(limit).all()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = self.db.query(AIModelCache).count()
        active_entries = self.db.query(AIModelCache).filter(
            AIModelCache.expires_at > datetime.utcnow()
        ).count()
        
        # Calculate hit rate (simplified)
        total_hits = self.db.query(func.sum(AIModelCache.hit_count)).scalar() or 0
        hit_rate = (total_hits / max(1, total_entries)) * 100 if total_entries > 0 else 0
        
        return {
            "total_entries": total_entries,
            "active_entries": active_entries,
            "hit_rate": hit_rate,
            "total_hits": total_hits
        }
