"""CNN-based freshness classification for producer/retailer scans."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow.keras import models

logger = logging.getLogger(__name__)


@dataclass
class FreshnessPrediction:
    score: float
    category: str
    confidence: float
    message: str
    dominant_class: Optional[str] = None
    dominant_score: Optional[float] = None


class FreshnessClassifier:
    def __init__(
        self,
        model_path: str,
        image_size: int = 100,
        threshold_fresh: float = 0.10,
        threshold_medium: float = 0.35,
    ) -> None:
        self.model_path = Path(model_path)
        self.image_size = image_size
        self.threshold_fresh = threshold_fresh
        self.threshold_medium = threshold_medium
        self.model: Optional[keras.Model] = None
        self._load_model()

    def _load_model(self) -> None:
        if not self.model_path.exists():
            logger.warning("Freshness model not found at %s", self.model_path)
            return
        try:
            self.model = models.load_model(self.model_path)
            logger.info("Freshness model loaded from %s", self.model_path)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to load freshness model: %s", exc)
            self.model = None

    @property
    def ready(self) -> bool:
        return self.model is not None

    def _classify(self, score: float) -> FreshnessPrediction:
        if score < self.threshold_fresh:
            category = "FRESH"
            message = "Sample is fresh"
            confidence = (self.threshold_fresh - score) / self.threshold_fresh
        elif score < self.threshold_medium:
            category = "MEDIUM FRESH"
            message = "Sample freshness is borderline"
            band_center = (self.threshold_fresh + self.threshold_medium) / 2
            confidence = 1 - abs(score - band_center) / ((self.threshold_medium - self.threshold_fresh) / 2)
        else:
            category = "NOT FRESH"
            message = "Sample is not fresh"
            confidence = (score - self.threshold_medium) / (1 - self.threshold_medium)
        return FreshnessPrediction(
            score=score,
            category=category,
            confidence=max(0.0, min(1.0, confidence)),
            message=message,
        )

    def predict(self, image_bytes: bytes) -> FreshnessPrediction:
        if not self.ready:
            raise RuntimeError("Freshness model is not loaded")

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError("Invalid image data provided") from exc

        image = image.resize((self.image_size, self.image_size))
        array = np.asarray(image, dtype=np.float32) / 255.0
        array = np.expand_dims(array, axis=0)

        prediction = self.model.predict(array, verbose=0)
        score = float(prediction[0][0])
        classification = self._classify(score)
        return classification
