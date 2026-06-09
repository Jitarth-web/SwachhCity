"""
Fixed version of AI Service with different port to avoid conflicts.
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

if __name__ == "__main__":
    import uvicorn
    print("Starting SwachhGram AI Service (Fixed Version)...")
    print("Available endpoints:")
    print("  GET  /")
    print("  GET  /health")
    print("  POST /classify")
    print("\nStarting server on http://localhost:8002")
    
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
