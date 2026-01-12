"""Hybrid Arrhenius + ML shelf-life predictor."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

R = 8.314  # Gas constant J/mol·K
T_REF_C = 5.0
T_REF_K = T_REF_C + 273.15
OPTIMAL_RH = 90.0

ALPHA_CONFIG = {
    "base": 0.35,
    "min": 0.1,
    "max": 0.8,
    "sensor_weight": 0.30,
    "ml_weight": 0.40,
    "history_limit": 120,
}

KINETIC_DATA: Dict[str, Dict[str, float]] = {
    "apple": {"Ea": 70000.0, "A": 2.0e11, "ref_life_days": 60},
    "banana": {"Ea": 62000.0, "A": 9.0e9, "ref_life_days": 14},
    "tomato": {"Ea": 36000.0, "A": 1.5e5, "ref_life_days": 14},
    "mango": {"Ea": 46000.0, "A": 2.5e7, "ref_life_days": 12},
    "potato": {"Ea": 60000.0, "A": 4.0e10, "ref_life_days": 90},
}


@dataclass
class ShelfLifeResult:
    ml_prediction: float
    arrhenius_prediction: float
    hybrid_prediction: float
    alpha_used: float
    sensor_temperature: float
    sensor_humidity: float
    sensor_samples: int
    sensor_stability: float
    ml_performance: float


class ShelfLifePredictor:
    def __init__(self, model_path: str, history_path: str) -> None:
        self.model_path = Path(model_path)
        self.history_path = Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.model = self._load_model()

    def _load_model(self):
        if not self.model_path.exists():
            raise FileNotFoundError(f"Shelf life model missing at {self.model_path}")
        logger.info("Loading shelf-life model from %s", self.model_path)
        return joblib.load(self.model_path)

    # ------------------------------- History utilities ------------------
    def _load_history(self) -> List[Dict]:
        if not self.history_path.exists():
            return []
        try:
            return json.loads(self.history_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to parse history file: %s", exc)
            return []

    def _save_history(self, history: List[Dict]) -> None:
        payload = history[-ALPHA_CONFIG["history_limit"] :]
        self.history_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _append_history(self, entry: Dict) -> None:
        history = self._load_history()
        history.append(entry)
        self._save_history(history)

    # ------------------------------- Physics helpers -------------------
    @staticmethod
    def _arrhenius_rate_constant(Ea: float, A: float, temp_k: float) -> float:
        return A * np.exp(-Ea / (R * temp_k))

    def _arrhenius_prediction(self, fruit: str, temp_c: float, humidity: float) -> float:
        params = KINETIC_DATA.get(fruit)
        if not params:
            raise ValueError(f"Unsupported product type '{fruit}' for shelf-life prediction")
        temp_k = temp_c + 273.15
        k_input = self._arrhenius_rate_constant(params["Ea"], params["A"], temp_k)
        k_ref = self._arrhenius_rate_constant(params["Ea"], params["A"], T_REF_K)
        ratio = k_ref / k_input
        rh_adj = self._humidity_factor(humidity)
        return params["ref_life_days"] * ratio * rh_adj

    @staticmethod
    def _humidity_factor(humidity: float) -> float:
        rh = max(30.0, min(100.0, humidity))
        deviation = abs(rh - OPTIMAL_RH)
        return float(np.exp(-0.02 * (deviation ** 1.2)))

    # ------------------------------- Alpha logic -----------------------
    def _assess_sensor_stability(
        self,
        readings: Sequence[Dict[str, float]],
        fallback_temp: float,
        fallback_humidity: float,
    ) -> float:
        if not readings:
            return 0.5
        temps = [r.get("temperature", fallback_temp) for r in readings]
        hums = [r.get("humidity", fallback_humidity) for r in readings]
        if len(temps) < 2:
            return 0.6
        temp_cv = np.std(temps) / (np.mean(temps) + 1e-6)
        hum_cv = np.std(hums) / (np.mean(hums) + 1e-6)
        temp_score = max(0.0, 1 - temp_cv * 10)
        hum_score = max(0.0, 1 - hum_cv * 5)
        return (temp_score + hum_score) / 2

    def _assess_ml_performance(self, history: Sequence[Dict]) -> float:
        if not history:
            return 0.5
        validated = [h for h in history if h.get("actual_shelf_life")]
        if validated:
            scores = []
            for entry in validated[-20:]:
                actual = entry["actual_shelf_life"]
                predicted = entry.get("hybrid_prediction")
                if actual and predicted:
                    error = abs(actual - predicted) / max(actual, 1e-6)
                    scores.append(max(0.0, 1 - error))
            if scores:
                return float(np.mean(scores))
        recent = history[-10:]
        preds = [entry.get("ml_prediction") for entry in recent if entry.get("ml_prediction") is not None]
        if len(preds) > 1:
            consistency = 1 - (np.std(preds) / (np.mean(preds) + 1e-6))
            return float(max(0.0, min(1.0, consistency)))
        return 0.5

    def _calculate_alpha(
        self,
        sensor_stability: float,
        ml_performance: float,
        alpha_override: Optional[float] = None,
    ) -> float:
        if alpha_override is not None:
            return float(max(0.0, min(1.0, alpha_override)))
        alpha = ALPHA_CONFIG["base"]
        alpha += (sensor_stability - 0.5) * ALPHA_CONFIG["sensor_weight"]
        alpha -= (ml_performance - 0.5) * ALPHA_CONFIG["ml_weight"]
        return float(max(ALPHA_CONFIG["min"], min(ALPHA_CONFIG["max"], alpha)))

    # ------------------------------- ML prediction ---------------------
    def _ml_prediction(self, fruit: str, temp_c: float, humidity: float) -> float:
        if not hasattr(self.model, "feature_names_in_"):
            raise ValueError("Loaded ML model is missing feature metadata")
        feature_columns = list(self.model.feature_names_in_)
        payload = {"Temperature_C": temp_c, "Humidity_%": humidity}
        for column in feature_columns:
            if column.startswith("Type_"):
                payload[column] = 1 if column == f"Type_{fruit.capitalize()}" else 0
        df = pd.DataFrame([payload])
        df = df.reindex(columns=feature_columns, fill_value=0)
        prediction = float(self.model.predict(df)[0])
        return prediction

    # ------------------------------- Public API -----------------------
    def predict(
        self,
        product_type: str,
        temperature_c: float,
        humidity_percent: float,
        sensor_readings: Optional[Sequence[Dict[str, float]]] = None,
        alpha_override: Optional[float] = None,
        batch_id: Optional[str] = None,
    ) -> ShelfLifeResult:
        fruit = product_type.strip().lower()
        history = self._load_history()
        sensor_stability = self._assess_sensor_stability(sensor_readings or [], temperature_c, humidity_percent)
        ml_performance = self._assess_ml_performance(history)
        alpha = self._calculate_alpha(sensor_stability, ml_performance, alpha_override)

        ml_pred = self._ml_prediction(fruit, temperature_c, humidity_percent)
        arr_pred = self._arrhenius_prediction(fruit, temperature_c, humidity_percent)
        hybrid = alpha * arr_pred + (1 - alpha) * ml_pred

        entry = {
            "batch_id": batch_id,
            "fruit": fruit,
            "temperature": temperature_c,
            "humidity": humidity_percent,
            "ml_prediction": ml_pred,
            "arrhenius_prediction": arr_pred,
            "hybrid_prediction": hybrid,
            "alpha_used": alpha,
            "sensor_samples": len(sensor_readings or []),
        }
        self._append_history(entry)

        return ShelfLifeResult(
            ml_prediction=ml_pred,
            arrhenius_prediction=arr_pred,
            hybrid_prediction=hybrid,
            alpha_used=alpha,
            sensor_temperature=temperature_c,
            sensor_humidity=humidity_percent,
            sensor_samples=len(sensor_readings or []),
            sensor_stability=sensor_stability,
            ml_performance=ml_performance,
        )

    def summarise_history(self) -> Dict[str, float]:
        history = self._load_history()
        if not history:
            return {"entries": 0}
        recent = history[-10:]
        avg_alpha = float(np.mean([entry.get("alpha_used", ALPHA_CONFIG["base"]) for entry in recent]))
        avg_ml = float(np.mean([entry.get("ml_prediction", 0.0) for entry in recent]))
        return {
            "entries": len(history),
            "recent_alpha": avg_alpha,
            "recent_ml_prediction": avg_ml,
        }
