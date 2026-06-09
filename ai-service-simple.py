#!/usr/bin/env python3
"""
Simple AI Service for SwachhGram - Waste Detection
A simplified version that works without complex dependencies
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import base64
import random
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SwachhGram Simple AI Service",
    description="Simple waste detection AI service",
    version="1.0.0"
)

# Apply CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Waste categories for detection
WASTE_CATEGORIES = [
    "illegal_dumping",
    "overflowing_bins", 
    "construction_debris",
    "medical_waste",
    "electronic_waste",
    "plastic_waste",
    "organic_waste",
    "hazardous_waste"
]

# Waste types and descriptions
WASTE_TYPES = {
    "illegal_dumping": {
        "type": "Illegal Dumping",
        "description": "Unauthorized waste disposal in public areas",
        "priority": "high"
    },
    "overflowing_bins": {
        "type": "Overflowing Bins", 
        "description": "Waste containers that are full and overflowing",
        "priority": "medium"
    },
    "construction_debris": {
        "type": "Construction Debris",
        "description": "Building materials and construction waste",
        "priority": "medium"
    },
    "medical_waste": {
        "type": "Medical Waste",
        "description": "Healthcare and medical waste materials",
        "priority": "high"
    },
    "electronic_waste": {
        "type": "E-Waste",
        "description": "Electronic and electrical waste items",
        "priority": "medium"
    },
    "plastic_waste": {
        "type": "Plastic Waste",
        "description": "Plastic and polymer waste materials",
        "priority": "low"
    },
    "organic_waste": {
        "type": "Organic Waste",
        "description": "Food and biodegradable waste",
        "priority": "low"
    },
    "hazardous_waste": {
        "type": "Hazardous Waste",
        "description": "Dangerous and toxic waste materials",
        "priority": "high"
    }
}

class WasteClassificationRequest(BaseModel):
    image_data: str
    image_type: str = "waste_detection"

class WasteClassificationResponse(BaseModel):
    id: str
    predicted_category: str
    confidence_score: float
    waste_type: str
    priority_level: str
    description: str
    processing_time_ms: float
    created_at: str

# Simulate AI waste detection
def simulate_waste_detection(image_data: str) -> Dict[str, Any]:
    """Simulate AI waste detection with realistic results"""
    
    # Extract basic image info (in real AI, this would be analyzed)
    image_size = len(image_data)
    
    # Simulate processing time
    processing_time = random.uniform(500, 2000)  # 0.5-2 seconds
    
    # Simulate detection confidence based on image characteristics
    base_confidence = random.uniform(0.6, 0.95)
    
    # Adjust confidence based on image size (larger images = better detection)
    if image_size > 100000:  # Large image
        confidence_adjustment = random.uniform(0.05, 0.1)
    elif image_size < 50000:  # Small image
        confidence_adjustment = random.uniform(-0.1, -0.05)
    else:
        confidence_adjustment = random.uniform(-0.02, 0.02)
    
    confidence_score = max(0.5, min(0.98, base_confidence + confidence_adjustment))
    
    # Select waste category (weighted towards common types)
    weights = [0.25, 0.20, 0.15, 0.05, 0.10, 0.10, 0.10, 0.05]  # Probability weights
    predicted_category = random.choices(WASTE_CATEGORIES, weights=weights)[0]
    
    # Get waste info
    waste_info = WASTE_TYPES[predicted_category]
    
    return {
        "predicted_category": predicted_category,
        "confidence_score": confidence_score,
        "waste_type": waste_info["type"],
        "priority_level": waste_info["priority"],
        "description": waste_info["description"],
        "processing_time_ms": processing_time
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "SwachhGram Simple AI Service",
        "version": "1.0.0",
        "status": "running",
        "capabilities": ["waste_detection", "image_classification"],
        "supported_categories": WASTE_CATEGORIES
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "ai-service-simple"
    }

@app.post("/classify", response_model=WasteClassificationResponse)
async def classify_image(request: WasteClassificationRequest):
    """Classify waste image using simulated AI"""
    try:
        logger.info(f"Received image classification request: {request.image_type}")
        
        # Validate input
        if not request.image_data:
            raise HTTPException(status_code=400, detail="Image data is required")
        
        # Remove data URL prefix if present
        if request.image_data.startswith('data:image/'):
            # Extract base64 part after comma
            if ',' in request.image_data:
                image_data = request.image_data.split(',')[1]
            else:
                image_data = request.image_data
        else:
            image_data = request.image_data
        
        # Simulate AI detection
        start_time = datetime.utcnow()
        detection_result = simulate_waste_detection(image_data)
        end_time = datetime.utcnow()
        
        # Calculate actual processing time
        processing_time = (end_time - start_time).total_seconds() * 1000
        
        # Create response
        response = WasteClassificationResponse(
            id=f"detection_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}",
            predicted_category=detection_result["predicted_category"],
            confidence_score=detection_result["confidence_score"],
            waste_type=detection_result["waste_type"],
            priority_level=detection_result["priority_level"],
            description=detection_result["description"],
            processing_time_ms=processing_time,
            created_at=datetime.utcnow().isoformat()
        )
        
        logger.info(f"Classification completed: {response.predicted_category} (confidence: {response.confidence_score:.2f})")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification error: {e}")
        raise HTTPException(status_code=500, detail="Classification failed")

@app.get("/categories")
async def get_categories():
    """Get all supported waste categories"""
    categories = []
    for category in WASTE_CATEGORIES:
        info = WASTE_TYPES[category]
        categories.append({
            "category": category,
            "type": info["type"],
            "description": info["description"],
            "priority": info["priority"]
        })
    
    return {"categories": categories}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007, reload=True)
