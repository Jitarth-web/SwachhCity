"""
Simplified test version of AI Service for demonstration.
IEEE Std 830-1998 SRS compliant test implementation.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import logging
import random
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SwachhGram AI Service - Test Version",
    description="AI & Analytics Service for SwachhGram (Test Mode)",
    version="1.0.0-test",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Apply CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Waste categories
WASTE_CATEGORIES = ["plastic", "organic", "hazardous", "mixed"]

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "SwachhGram AI Service - Test Version", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0-test",
        "models_loaded": {
            "classification": True,
            "optimization": True,
            "prediction": True
        },
        "gpu_available": False,  # Test mode
        "cpu_usage_percent": 25.5,  # Test data
        "memory_usage_mb": 512.3,  # Test data
        "cache_size": 100,  # Test data
        "queue_length": 0
    }

@app.post("/classify")
async def classify_image(classification_request: dict):
    """Classify waste image using AI (test version)."""
    try:
        image_url = classification_request.get("image_url")
        if not image_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image URL is required"
            )
        
        # Simulate processing time
        start_time = time.time()
        time.sleep(0.5)  # Simulate AI processing
        processing_time = int((time.time() - start_time) * 1000)
        
        # Generate random classification
        predicted_category = random.choice(WASTE_CATEGORIES)
        confidence_score = round(random.uniform(0.7, 0.95), 3)
        
        # Generate probabilities for all categories
        remaining_confidence = 1.0 - confidence_score
        other_probabilities = [random.uniform(0, remaining_confidence) for _ in range(3)]
        other_probabilities = [p / sum(other_probabilities) * remaining_confidence for p in other_probabilities]
        
        category_probabilities = {}
        categories_copy = WASTE_CATEGORIES.copy()
        categories_copy.remove(predicted_category)
        
        category_probabilities[predicted_category] = confidence_score
        for i, category in enumerate(categories_copy):
            category_probabilities[category] = round(other_probabilities[i], 3)
        
        # Image quality assessment
        image_quality_score = round(random.uniform(60, 95), 1)
        blur_detected = random.choice([True, False])
        lighting_quality = random.choice(["good", "bright", "dark"])
        
        result = {
            "id": str(uuid.uuid4()),
            "image_url": image_url,
            "predicted_category": predicted_category,
            "confidence_score": confidence_score,
            "category_probabilities": category_probabilities,
            "processing_time_ms": processing_time,
            "model_id": str(uuid.uuid4()),
            "model_version": "1.0.0-test",
            "image_quality_score": image_quality_score,
            "blur_detected": blur_detected,
            "lighting_quality": lighting_quality,
            "verified_by_human": False,
            "created_at": datetime.utcnow()
        }
        
        logger.info(f"Image classified: {predicted_category} with confidence {confidence_score}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Classification failed"
        )

@app.post("/classify/batch")
async def batch_classify_images(batch_request: dict):
    """Batch classify multiple images."""
    try:
        image_urls = batch_request.get("image_urls", [])
        if not image_urls:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image URLs are required"
            )
        
        start_time = time.time()
        results = []
        successful = 0
        failed = 0
        
        for image_url in image_urls:
            try:
                # Classify each image
                classification = await classify_image({"image_url": image_url})
                results.append(classification)
                successful += 1
            except Exception as e:
                logger.error(f"Batch classification failed for {image_url}: {e}")
                failed += 1
        
        total_processing_time = int((time.time() - start_time) * 1000)
        avg_processing_time = total_processing_time / len(image_urls) if image_urls else 0
        
        return {
            "request_id": str(uuid.uuid4()),
            "results": results,
            "total_processed": len(image_urls),
            "successful": successful,
            "failed": failed,
            "total_processing_time_ms": total_processing_time,
            "avg_processing_time_ms": avg_processing_time,
            "created_at": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch classification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch classification failed"
        )

@app.post("/optimize/routes")
async def optimize_routes(optimization_request: dict):
    """Optimize collection routes using AI (test version)."""
    try:
        truck_locations = optimization_request.get("truck_locations", [])
        pickup_locations = optimization_request.get("pickup_locations", [])
        
        if not truck_locations or not pickup_locations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Truck and pickup locations are required"
            )
        
        start_time = time.time()
        
        # Simulate optimization processing
        time.sleep(1.0)  # Simulate AI processing
        
        # Simple assignment: distribute pickups evenly among trucks
        optimized_routes = {}
        pickups_per_truck = len(pickup_locations) // len(truck_locations)
        
        for i, truck in enumerate(truck_locations):
            truck_id = truck.get("id", f"truck_{i}")
            start_idx = i * pickups_per_truck
            end_idx = start_idx + pickups_per_truck
            
            if i == len(truck_locations) - 1:  # Last truck gets remaining
                end_idx = len(pickup_locations)
            
            route_pickups = pickup_locations[start_idx:end_idx]
            
            # Calculate route metrics
            route_distance = len(route_pickups) * random.uniform(3, 8)  # 3-8km per pickup
            route_time = route_distance * 2  # 2 min per km
            
            optimized_routes[truck_id] = {
                "route": route_pickups,
                "distance": round(route_distance, 2),
                "time": round(route_time, 0)
            }
        
        total_distance = sum(route["distance"] for route in optimized_routes.values())
        total_time = sum(route["time"] for route in optimized_routes.values())
        
        # Calculate savings
        baseline_distance = len(pickup_locations) * 5.5  # Baseline 5.5km per pickup
        distance_savings = baseline_distance - total_distance
        
        processing_time = int((time.time() - start_time) * 1000)
        
        result = {
            "id": str(uuid.uuid4()),
            "optimization_request_id": str(uuid.uuid4()),
            "optimized_routes": optimized_routes,
            "total_distance_km": round(total_distance, 2),
            "estimated_time_minutes": int(total_time),
            "distance_savings_km": round(max(0, distance_savings), 2),
            "time_savings_minutes": int(max(0, distance_savings * 2)),
            "efficiency_improvement": round((distance_savings / baseline_distance * 100) if baseline_distance > 0 else 0, 2),
            "algorithm_used": optimization_request.get("algorithm", "hybrid"),
            "processing_time_ms": processing_time,
            "iterations": random.randint(10, 50),
            "convergence_score": round(random.uniform(0.8, 0.95), 3),
            "status": "completed",
            "created_at": datetime.utcnow()
        }
        
        logger.info(f"Route optimization completed: {result['algorithm_used']} algorithm, {result['total_distance_km']}km total")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Route optimization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route optimization failed"
        )

@app.post("/predict/hotspots")
async def predict_hotspots(prediction_request: dict):
    """Predict waste collection hotspots (test version)."""
    try:
        analysis_type = prediction_request.get("analysis_type", "hotspot")
        target_date = prediction_request.get("target_date")
        prediction_horizon_days = prediction_request.get("prediction_horizon_days", 30)
        
        if not target_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target date is required"
            )
        
        start_time = time.time()
        
        # Simulate prediction processing
        time.sleep(0.8)  # Simulate AI processing
        
        # Generate sample hotspot predictions
        hotspots = []
        num_hotspots = random.randint(5, 15)
        
        for i in range(num_hotspots):
            hotspot = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        round(random.uniform(77.5, 77.7), 6),  # Longitude (Bangalore area)
                        round(random.uniform(12.9, 13.1), 6)   # Latitude (Bangalore area)
                    ]
                },
                "properties": {
                    "ward_id": f"ward_{random.randint(1, 8)}",
                    "intensity": round(random.uniform(0.3, 0.9), 3),
                    "predicted_waste_amount": round(random.uniform(20, 150), 1),
                    "confidence": round(random.uniform(0.6, 0.9), 3),
                    "prediction_date": target_date
                }
            }
            hotspots.append(hotspot)
        
        prediction_data = {
            "type": "FeatureCollection",
            "features": hotspots
        }
        
        processing_time = int((time.time() - start_time) * 1000)
        
        result = {
            "id": str(uuid.uuid4()),
            "analysis_type": analysis_type,
            "target_date": target_date,
            "prediction_data": prediction_data,
            "confidence_level": round(random.uniform(0.7, 0.9), 3),
            "prediction_horizon_days": prediction_horizon_days,
            "model_id": str(uuid.uuid4()),
            "model_version": "1.0.0-test",
            "historical_accuracy": round(random.uniform(0.75, 0.85), 3),
            "processing_time_ms": processing_time,
            "data_points_used": random.randint(500, 2000),
            "data_quality_score": round(random.uniform(0.7, 0.9), 3),
            "status": "active",
            "created_at": datetime.utcnow()
        }
        
        logger.info(f"Hotspot prediction completed: {len(hotspots)} hotspots predicted")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hotspot prediction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed"
        )

@app.get("/metrics")
async def get_metrics():
    """Get AI service metrics."""
    return {
        "total_classifications_today": random.randint(50, 200),
        "total_optimizations_today": random.randint(10, 30),
        "total_predictions_today": random.randint(5, 15),
        "avg_processing_time_ms": round(random.uniform(800, 2000), 1),
        "cache_hit_rate": round(random.uniform(60, 85), 1),
        "model_accuracy_rates": {
            "classification": round(random.uniform(0.85, 0.95), 3),
            "optimization": round(random.uniform(0.80, 0.90), 3),
            "prediction": round(random.uniform(0.75, 0.85), 3)
        },
        "gpu_utilization_percent": round(random.uniform(20, 60), 1),
        "memory_utilization_percent": round(random.uniform(40, 70), 1),
        "active_models": 3,
        "queue_length": 0
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting SwachhGram AI Service (Test Version)...")
    print("Available endpoints:")
    print("  GET  /")
    print("  GET  /health")
    print("  POST /classify")
    print("  POST /classify/batch")
    print("  POST /optimize/routes")
    print("  POST /predict/hotspots")
    print("  GET  /metrics")
    print("\nStarting server on http://localhost:8001")
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
