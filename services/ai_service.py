"""
AI Service for freshness analysis
Provides async wrapper for FreshnessClassifier
"""
import base64
from typing import Dict, Any
from services.freshness_classifier import FreshnessClassifier, FreshnessPrediction

# Initialize classifier (singleton pattern)
_classifier = None

def get_classifier() -> FreshnessClassifier:
    """Get or initialize the freshness classifier"""
    global _classifier
    if _classifier is None:
        _classifier = FreshnessClassifier()
    return _classifier


async def analyze_freshness(image_base64: str) -> Dict[str, Any]:
    """
    Analyze freshness from base64 encoded image
    
    Args:
        image_base64: Base64 encoded image string (without data URI prefix)
        
    Returns:
        Dictionary with freshness analysis results:
        - freshness_score: float (0-100)
        - category: str (Fresh/Moderate/Rotten)
        - confidence: float (0-1)
    """
    try:
        # Decode base64 to bytes
        image_bytes = base64.b64decode(image_base64)
        
        # Get classifier and predict
        classifier = get_classifier()
        prediction: FreshnessPrediction = classifier.predict(image_bytes)
        
        return {
            "freshness_score": prediction.score,
            "category": prediction.category,
            "confidence": prediction.confidence
        }
    except Exception as e:
        # Return default values on error
        return {
            "freshness_score": 0,
            "category": "Unknown",
            "confidence": 0.0,
            "error": str(e)
        }
