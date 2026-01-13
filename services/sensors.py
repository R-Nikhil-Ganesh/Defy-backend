"""Sensor registry and telemetry persistence."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from schemas import SensorType

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


class SensorRegistry:
    """Persistent, file-backed sensor registry for transport and retail sensors."""

    def __init__(self, state_path: str):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._state: Dict[str, Any] = {
            "sensors": {},
            "sensorLinks": {},
            "batchLinks": {},
            "readings": {},
        }
        self._load_state()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load_state(self) -> None:
        if self.state_path.exists():
            try:
                self._state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                # Corrupted state – fall back to empty store
                self._state = {"sensors": {}, "sensorLinks": {}, "batchLinks": {}, "readings": {}}
        else:
            self.state_path.write_text(json.dumps(self._state), encoding="utf-8")

    def _write_state(self) -> None:
        tmp_path = self.state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        tmp_path.replace(self.state_path)

    # ------------------------------------------------------------------
    # Sensor lifecycle
    # ------------------------------------------------------------------
    async def register_sensor(
        self,
        sensor_id: str,
        sensor_type: SensorType,
        owner_username: str,
        label: Optional[str] = None,
        vehicle_or_store_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        async with self._lock:
            sensor_payload = {
                "sensorId": sensor_id,
                "sensorType": sensor_type.value,
                "label": label,
                "vehicleOrStoreId": vehicle_or_store_id,
                "metadata": metadata or {},
                "owner": owner_username,
                "registeredAt": _now_iso(),
                "lastHeartbeat": None,
            }
            self._state["sensors"][sensor_id] = sensor_payload
            self._write_state()
            return sensor_payload

    async def get_sensor(self, sensor_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            return self._state["sensors"].get(sensor_id)

    async def link_sensor(
        self,
        sensor_id: str,
        batch_id: str,
        location_type: SensorType,
        linked_by: str,
    ) -> Dict[str, Any]:
        async with self._lock:
            if sensor_id not in self._state["sensors"]:
                raise ValueError(f"Sensor {sensor_id} is not registered")

            # AUTO-UNLINK: When linking a new location type (e.g., retailer), unlink the previous one (e.g., transporter)
            batch_links = self._state["batchLinks"].setdefault(batch_id, {})
            existing_binding = batch_links.get(location_type.value)
            
            if existing_binding:
                old_sensor_id = existing_binding.get("sensorId")
                if old_sensor_id and old_sensor_id != sensor_id:
                    # Unlink the old sensor for this location type
                    self._state["sensorLinks"].pop(old_sensor_id, None)
                    logger.info(f"Auto-unlinked {old_sensor_id} from batch {batch_id} ({location_type.value})")

            binding = {
                "sensorId": sensor_id,
                "batchId": batch_id,
                "locationType": location_type.value,
                "linkedBy": linked_by,
                "linkedAt": _now_iso(),
            }

            self._state["sensorLinks"][sensor_id] = binding
            batch_links[location_type.value] = binding
            self._write_state()
            
            logger.info(f"Linked {sensor_id} to batch {batch_id} ({location_type.value}) by {linked_by}")
            return binding

    async def unlink_batch(self, batch_id: str, location_type: SensorType) -> None:
        async with self._lock:
            batch_links = self._state["batchLinks"].get(batch_id)
            if not batch_links:
                return
            binding = batch_links.pop(location_type.value, None)
            if binding:
                self._state["sensorLinks"].pop(binding["sensorId"], None)
            if not batch_links:
                self._state["batchLinks"].pop(batch_id, None)
            self._write_state()

    # ------------------------------------------------------------------
    # Telemetry ingestion
    # ------------------------------------------------------------------
    async def record_reading(
        self,
        sensor_id: str,
        temperature: float,
        humidity: float,
        source: str,
        batch_id: Optional[str] = None,
        captured_at: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], int]:
        async with self._lock:
            sensor = self._state["sensors"].get(sensor_id)
            if not sensor:
                raise ValueError(f"Sensor {sensor_id} is not registered")

            binding = self._state["sensorLinks"].get(sensor_id)
            resolved_batch = batch_id or (binding["batchId"] if binding else None)
            if not resolved_batch:
                raise ValueError("Sensor is not linked to any batch. Scan the QR first.")

            sensor_type_value = (binding or {}).get("locationType") or sensor.get("sensorType")
            if sensor_type_value not in (SensorType.TRANSPORTER.value, SensorType.RETAILER.value):
                raise ValueError("Unsupported sensor type")

            entry = {
                "batchId": resolved_batch,
                "sensorId": sensor_id,
                "sensorType": sensor_type_value,
                "temperature": temperature,
                "humidity": humidity,
                "capturedAt": captured_at or _now_iso(),
                "source": source,
            }

            readings = self._state["readings"].setdefault(resolved_batch, [])
            readings.append(entry)
            if len(readings) > 200:
                self._state["readings"][resolved_batch] = readings[-200:]
            sensor["lastHeartbeat"] = entry["capturedAt"]
            self._write_state()
            return entry, len(self._state["readings"][resolved_batch])

    async def get_batch_readings(self, batch_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        async with self._lock:
            readings = self._state["readings"].get(batch_id, [])
            return list(reversed(readings))[:limit]
    
    async def get_recent_readings_for_average(self, batch_id: str, minutes: int = 30) -> List[Dict[str, Any]]:
        """Get readings from the last N minutes for averaging"""
        async with self._lock:
            readings = self._state["readings"].get(batch_id, [])
            if not readings:
                return []
            
            # Calculate cutoff time
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            
            # Filter readings within the time window
            recent = []
            for reading in reversed(readings):  # Most recent first
                try:
                    captured_at = datetime.fromisoformat(reading["capturedAt"].replace("Z", "+00:00"))
                    if captured_at >= cutoff:
                        recent.append(reading)
                except Exception:
                    continue
            
            return recent

    async def get_batch_bindings(self, batch_id: str) -> Dict[str, Any]:
        async with self._lock:
            return self._state["batchLinks"].get(batch_id, {}).copy()

    async def get_sensor_binding(self, sensor_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            binding = self._state["sensorLinks"].get(sensor_id)
            return binding.copy() if binding else None

    async def list_sensors(self, sensor_type: Optional[SensorType] = None, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered sensors, optionally filtered by type or owner"""
        async with self._lock:
            sensors = []
            for sensor_id, sensor_data in self._state["sensors"].items():
                if sensor_type and sensor_data.get("sensorType") != sensor_type.value:
                    continue
                if owner and sensor_data.get("owner") != owner:
                    continue
                
                # Check if sensor is currently linked
                binding = self._state["sensorLinks"].get(sensor_id)
                sensor_info = sensor_data.copy()
                sensor_info["isLinked"] = binding is not None
                sensor_info["currentBatch"] = binding.get("batchId") if binding else None
                sensors.append(sensor_info)
            
            return sensors

    async def list_sensors(self, sensor_type: Optional[SensorType] = None, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered sensors, optionally filtered by type or owner"""
        async with self._lock:
            sensors = []
            for sensor_id, sensor_data in self._state["sensors"].items():
                if sensor_type and sensor_data.get("sensorType") != sensor_type.value:
                    continue
                if owner and sensor_data.get("owner") != owner:
                    continue
                
                # Check if sensor is currently linked
                binding = self._state["sensorLinks"].get(sensor_id)
                sensor_info = sensor_data.copy()
                sensor_info["isLinked"] = binding is not None
                sensor_info["currentBatch"] = binding.get("batchId") if binding else None
                sensors.append(sensor_info)
            
            return sensors
